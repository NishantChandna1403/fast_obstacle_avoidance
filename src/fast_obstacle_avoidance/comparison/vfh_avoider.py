""" Implementation of the vector field histogram (VFH) algorithm.

This code has been copied from:
https://github.com/vanderbiltrobotics/vfh-python

(No fork / sub-module, due to inactivity for several years and somehow very large git repo/history.)
"""

import warnings
import math

import numpy as np
from numpy import linalg as LA

import matlab

# from fast_obstacle_avoidance.obstacle_avoider._base import SampledAvoider
from fast_obstacle_avoidance.obstacle_avoider.lidar_avoider import SampledAvoider

# from ._base import SingleModulationAvoider
from fast_obstacle_avoidance.comparison.vfh_python.lib.robot import Robot as VFH_Robot
from fast_obstacle_avoidance.comparison.vfh_python.lib.polar_histogram import (
    PolarHistogram,
)
from fast_obstacle_avoidance.comparison.vfh_python.lib.path_planner import (
    PathPlanner as VFH_Planner,
)


class VFH_Avoider_Matlab:
    def __init__(
        self,
        num_angular_sectors: int = 180,
        robot=None,
        distance_limits: float = (0.05, 2),
        robot_radius: float = 0.1,
        min_turning_radius: float = 0.1,
        safety_distance: float = 0.1,
        matlab_engine=None,
    ):
        self.robot = robot

        self.angles = None
        self.ranges = None
        self.datapoints = None

        if matlab_engine is None:
            # Start engine if no engine past
            import matlab.engine

            matlab_engine = matlab.engine.start_matlab()

            # Add local helper-files to path
            matlab_engine.addpath("src/fast_obstacle_avoidance/comparison")

        self.matlab_engine = matlab_engine

    def update_reference_direction(self, *args, **kwargs):
        warnings.warn("Not performing anything.")

    def avoid(self, initial_velocity):
        if not LA.norm(initial_velocity):
            return

        target_dir = np.arctan2(initial_velocity[1], initial_velocity[0])
        m_steering_direction = self.matlab_engine.vfh_func(
            matlab.double(self.ranges),
            matlab.double(self.angles),
            target_dir,
            {"RobotRadius": self.robot.control_radius},
        )
        # self.m_vfh.UseLidarScan = True
        # m_steering_direction = self.m_vfh(m_scan, target_dir)
        steering_direction = float(m_steering_direction)
        output_velocity = np.array(
            [math.cos(m_steering_direction), math.sin(m_steering_direction)]
        ) * LA.norm(initial_velocity)

        return output_velocity

    def update_laserscan(self, points, in_robot_frame=False):
        if in_robot_frame:
            self.datapoints = self.robot.pose.transform_position_from_relative(points)
            # Set global datapoints
        else:
            self.datapoints = points
            points = self.robot.pose.transform_position_to_relative(points)

        self.angles = np.arctan2(points[1, :], points[0, :])
        self.ranges = LA.norm(points, axis=0)
        breakpoint()


class VectorFieldHistogramAvoider(SampledAvoider):
    def __init__(
        self,
        num_angular_sectors: int = 180,
        distance_limits: float = (0.05, 2),
        robot_radius: float = 0.1,
        min_turning_radius: float = 0.1,
        safety_distance: float = 0.1,
        attractor_position: np.ndarray = None,
    ):

        self.num_angular_sectors = num_angular_sectors
        # num_angular_sectors:int = 180,
        # distance_limits: float = (0.05, 2),
        # robot_radius: float = 0.1,
        # min_turning_radius: float = 0.1,
        # safety_distance: float = 0.1,

        if attractor_position is None:
            # Assuming 2D
            attractor_position = np.zeros([0, 0])

        breakpoint()
        new_grid = HistogramGrid()

        self.vfh_histogram = PolarHistogram(num_bins=num_angular_sectors)
        self.vfh_robot = VFH_Robot(
            target_location=attractor_position,
            init_speed=np.zeros(attractor_position.shape),
        )

    @property
    def attractor_position(self) -> np.ndarray:
        return self._attractor_position

    @attractor_position.setter
    def attractor_position(self, value) -> None:
        breakpoint()
        self.vfh_robot.set_target_discrete_location(value)
        self._attractor_position = vaue

    def update_laserscan(self):
        self.vfh_robot.histogram

    def avoid(self, position, velocity):
        self.vfh_robot.update_location(position)

        # Make a step
        self.vfh_robot.bupdate_angle()  # angle: Null (or optionally, t-1) => t
        # self.set_speed() # speed: Null (or optionally, t-1) => t

        self.vfh_robot.update_velocity()
        self.vfh_robot.update_location()  # position: t => t+1

        return self.vfh_robot.velocity