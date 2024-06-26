"""
Simplified obstacle avoidance for mobile for mobile robots based on
DS & reference_direction

The algorithm is developed for shared control,
> human will know the best path, just be fast and don't get stuck
(make unexpected mistakes)
"""

import warnings

import numpy as np
from numpy import linalg as LA

from vartools.linalg import get_orthogonal_basis

from fast_obstacle_avoidance.control_robot import BaseRobot
from ._base import SingleModulationAvoider


class FastObstacleAvoider(SingleModulationAvoider):
    def __init__(
        self,
        obstacle_environment,
        robot: BaseRobot = None,
        # reference_update_before_modulation: bool = True,
        consider_relative_velocity: bool = True,
        weight_factor: float = 1,
        margin_weight: float = 1,
        distance_weight_sum: float = 1,
        dimension: int = 2,
        **kwargs
    ):
        """Initialize with obstacle list"""

        self.obstacle_environment = obstacle_environment
        self.robot = robot

        super().__init__(
            weight_factor=weight_factor, margin_weight=margin_weight, **kwargs
        )

        if (
            len(self.obstacle_environment) and self.obstacle_environment.dimension == 3
        ) or dimension == 2:
            from scipy.spatial.transform import Rotation as R

        # Simulation paramteres
        self.consider_relative_velocity = consider_relative_velocity

    def update_laserscan(self, *args, **kwargs):
        warnings.warn(
            "No action taken on update, we're waiting for the analytic description."
        )

    @property
    def dimension(self):
        return self.obstacle_environment.dimension

    def update_relative_velocity(
        self, weights, position, weight_pow=2, velocity_scaling=1.1
    ):
        """Update linear and angular velocity (without deformation)."""
        linear_velocities = np.zeros((self.dimension, weights.shape[0]))
        angular_velocities = np.zeros((weights.shape[0]))

        weights = weights**weight_pow
        weights = weights / np.sum(weights)

        summed_angular = np.zeros(position.shape[0])
        for it, obs in enumerate(self.obstacle_environment):
            if weights[it] <= 0:
                continue

            linear_velocities[:, it] = obs.linear_velocity

            if obs.angular_velocity and LA.norm(obs.angular_velocity):

                angular_weight = np.exp(1 - (1 / weights[it]))
                angular_vel = np.cross(
                    np.array([0, 0, obs.angular_velocity]),
                    np.hstack((position - np.array(obs.center_position), 0)),
                )

                summed_angular += angular_weight * angular_vel[:2]

        # if any(angular_velocities):
        # warnings.warn("Not yet implemented for angular velocity.")

        self.relative_velocity = np.sum(
            (np.tile(weights, (linear_velocities.shape[0], 1)) * linear_velocities),
            axis=1,
        )

        self.relative_velocity = self.relative_velocity + summed_angular

        # Try sure to move away a bit 'faster' than surface velocity
        self.relative_velocity = self.relative_velocity * velocity_scaling

        return self.relative_velocity

    def update_reference_direction(
        self, in_robot_frame=True, position=None, initial_velocity=None
    ):
        """Take position from robot position if not given as argument."""
        if not len(self.obstacle_environment):
            # No obstacles found -> default reference
            # By default we assume dim=2
            # TODO: specified for any other case (!)
            self.reference_direction = np.zeros(2)
            self.normal_direction = np.zeros(self.reference_direction.shape)
            self.norm_angle = np.zeros(self.reference_direction.shape[0] - 1)
            self.distance_weight_sum = 0
            return

        if position is None:
            if in_robot_frame:
                position = np.zeros(self.obstacle_environment.dimension)
            else:
                position = self.robot.pose.position

        norm_dirs = np.zeros(
            (self.obstacle_environment.dimension, self.obstacle_environment.n_obstacles)
        )
        ref_dirs = np.zeros(norm_dirs.shape)
        gammas = np.zeros((norm_dirs.shape[1]))

        # if self.consider_relative_velocity:
        # self.udpate_relative_velocity(weights, position=position)
        # relative_velocities = np.zeros(ref_dirs.shape)

        for it, obs in enumerate(self.obstacle_environment):
            norm_dirs[:, it] = obs.get_normal_direction(position, in_global_frame=True)
            ref_dirs[:, it] = (-1) * obs.get_reference_direction(
                position, in_global_frame=True
            )

            if obs.is_boundary:
                # Invert boundary-directions, as 'flowing' away from boundary is in the other direction
                ref_dirs[:, it] = (-1) * ref_dirs[:, it]
                norm_dirs[:, it] = (-1) * norm_dirs[:, it]

            gammas[it] = obs.get_gamma(position, in_global_frame=True)

        weights = self.get_weights_from_gamma(
            gammas, directions=ref_dirs, initial_velocity=initial_velocity
        )
        self.reference_direction = np.sum(
            ref_dirs * np.tile(weights, (ref_dirs.shape[0], 1)), axis=1
        )

        if any(np.isnan(self.reference_direction)):
            breakpoint()

        norm_ref_dir = LA.norm(self.reference_direction)
        if not norm_ref_dir:
            self.normal_direction = self.reference_direction
            return

        self.normal_direction = self.update_normal_direction(
            ref_dirs, norm_dirs, weights
        )

        if self.consider_relative_velocity:
            self.update_relative_velocity(weights=weights, position=position)

        if self.robot is not None:
            self.robot.retrieved_obstacles()

        if hasattr(self, "debug_mode") and self.debug_mode:
            warnings.warn("Storing refs and norms.")
            self.ref_dirs = ref_dirs
            self.normal_dirs = norm_dirs

            self.tang_dirs = np.vstack(
                ((-1) * self.normal_dirs[1, :], self.normal_dirs[0, :])
            )

    @property
    def tangent_direction(self):
        """Only works for two dimensions!!"""
        tang = np.array([(-1) * self.normal_direction[1], self.normal_direction[0]])
        tang = tang / LA.norm(tang) * LA.norm(self.reference_direction)
        return tang

    def update_normal_direction(self, ref_dirs, norm_dirs, weights) -> np.ndarray:
        """Update normal direction which is used in the decomposition of the initial velocity."""
        # Check if normal directions are valid
        ind_nonzero = LA.norm(norm_dirs, axis=0) > 0
        if not np.sum(ind_nonzero):
            if LA.norm(self.reference_direction):
                self.normal_direction = self.reference_direction / LA.norm(
                    self.reference_direction
                )
            else:
                self.normal_direction = (
                    np.ones(self.reference_direction.shape)
                    / self.reference_direction.shape[0]
                )

            return self.normal_direction

        ref_dirs = ref_dirs[:, ind_nonzero]
        norm_dirs = norm_dirs[:, ind_nonzero]
        weights = weights[ind_nonzero]

        delta_normals = norm_dirs - ref_dirs
        delta_normal = np.sum(
            delta_normals * np.tile(weights, (delta_normals.shape[0], 1)), axis=1
        )

        if not LA.norm(delta_normal) or not LA.norm(self.reference_direction):
            # Trivial case
            self.normal_direction = self.reference_direction
            normal_norm = LA.norm(self.normal_direction)
            if normal_norm:
                self.normal_direction = self.normal_direction / normal_norm
            return self.normal_direction

        dot_prod = (-1) * (
            np.dot(delta_normal, self.reference_direction)
            / (LA.norm(delta_normal) * LA.norm(self.reference_direction))
        )

        if dot_prod < np.sqrt(2) / 2:
            normal_scaling = 1
        else:
            normal_scaling = np.sqrt(2) * dot_prod

        self.normal_direction = (
            normal_scaling
            * self.reference_direction
            / LA.norm(self.reference_direction)
            + delta_normal
        )
        self.normal_direction = self.normal_direction / LA.norm(self.normal_direction)

        return self.normal_direction

    def update_normal_direction_with_relative_rotation(
        self, ref_dirs, norm_dirs, weights
    ) -> np.ndarray:
        """Update the normal direction of an obstacle.
        This approach is based on relative rotation, it would potentially be nicer,
        but we could not extend it to d>3."""
        if self.obstacle_environment.dimension == 2:
            norm_angles = np.cross(ref_dirs, norm_dirs, axisa=0, axisb=0)

            self.norm_angle = np.sum(norm_angles * weights)
            self.norm_angle = np.arcsin(self.norm_angle)

            # Add angle to reference direction
            unit_ref_dir = self.reference_direction / LA.norm(self.reference_direction)
            self.norm_angle += np.arctan2(unit_ref_dir[1], unit_ref_dir[0])

            self.normal_direction = np.array(
                [np.cos(self.norm_angle), np.sin(self.norm_angle)]
            )

        elif self.obstacle_environment.dimension == 3:
            norm_angles = np.cross(norm_dirs, ref_dirs, axisa=0, axisb=0)

            self.norm_angle = np.sum(
                norm_angles * np.tile(weights, (relative_position.shape[0], 1)), axis=1
            )
            norm_angle_mag = LA.norm(self.norm_angle)
            if not norm_angle_mag:  # Zero value
                self.normal_direction = copy.deepcopy(self.reference_direction)

            else:
                norm_rot = Rotation.from_vec(
                    self.normal_direction / norm_angle_mag * np.arcsin(norm_angle_mag)
                )

                unit_ref_dir = self.reference_direction / norm_ref_dir

                self.normal_direction = norm_rot.apply(unit_ref_dir)

        else:
            raise NotImplementedError(
                "For higher dimensions it is currently not defined."
            )

        return self.normal_direction

    def get_weights_from_gamma(
        self,
        gammas: np.ndarray,
        directions: np.ndarray = None,
        initial_velocity: np.ndarray = None,
        max_weight_value: float = 1e10,
        lower_margin: float = 1e-10,
    ):
        ref_dists = np.array(
            [oo.get_characteristic_length() for oo in self.obstacle_environment]
        )

        ind_zero = gammas < lower_margin
        if np.sum(ind_zero):
            weights = np.zeros(ind_zero.shape)
            weights[ind_zero] = 1 / np.sum(ind_zero)
            return weights

        # Distance weight * weight factor
        distance_weights = 1 / (gammas - 1)
        size_weights = (
            2 * ref_dists / (gammas - 1 + 2 * ref_dists) ** (self.dimension - 1)
        )
        # size_weights = 1
        weights = distance_weights * size_weights

        if (
            self.evaluate_velocity_weight
            and directions is not None
            and initial_velocity is not None
        ):
            weights = self.reduce_wake_effect(weights, initial_velocity, directions)

        self.distance_weight_sum = np.sum(weights)

        if self.distance_weight_sum > 1:
            return weights / self.distance_weight_sum
        else:
            return weights
