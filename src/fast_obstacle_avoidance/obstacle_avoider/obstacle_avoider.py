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
    def __init__(self, obstacle_environment, robot: BaseRobot = None, dimension=2):
        """Initialize with obstacle list"""
        self.obstacle_environment = obstacle_environment
        self.robot = robot

        super().__init__()

        if (
            len(self.obstacle_environment) and self.obstacle_environment.dimension == 3
        ) or dimension == 2:
            from scipy.spatial.transform import Rotation as R

    def update_reference_direction(self, in_robot_frame=True):
        if in_robot_frame:
            position = np.zeros(self.obstacle_environment.dimension)
        else:
            position = robot.pose.position

        norm_dirs = np.zeros(
            (self.obstacle_environment.dimension, self.obstacle_environment.n_obstacles)
        )
        ref_dirs = np.zeros(norm_dirs.shape)
        relative_distances = np.zeros((norm_dirs.shape[1]))

        # breakpoint()
        for it, obs in enumerate(self.obstacle_environment):
            norm_dirs[:, it] = obs.get_normal_direction(position, in_global_frame=True)

            ref_dirs[:, it] = (-1) * obs.get_reference_direction(
                position, in_global_frame=True
            )

            relative_distances[it] = obs.get_gamma(position, in_global_frame=True) - 1

        weights = self.get_weight_from_distances(relative_distances)

        self.reference_direction = np.sum(
            ref_dirs * np.tile(weights, (ref_dirs.shape[0], 1)), axis=1
        )

        norm_ref_dir = LA.norm(self.reference_direction)
        if not norm_ref_dir:
            self.normal_direction = np.zeros(reference_direction.shape)
            return

        self.normal_direction = self.update_normal_direction(
            ref_dirs, norm_dirs, weights
        )

        if self.robot is not None:
            self.robot.retrieved_obstacles()

    def update_normal_direction(self, ref_dirs, norm_dirs, weights) -> np.ndarray:
        """Update the normal direction of an obstacle."""
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
