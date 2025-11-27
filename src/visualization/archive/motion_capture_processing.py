from __future__ import annotations  #타입 힌트가 문자열로 처리되기 때문에 순환 참조 문제가 발생하지 않습니다.

'''
Motion Capture 후 marker csv data parsing
'''
'''
Motion Capture 후 marker csv data parsing 및 직사각형 메쉬 생성
'''
import os
import pandas as pd
import numpy as np
import vtk
import pyvista as pv  # PyVista를 사용하여 VTK 파일 시각화
from pyvistaqt import BackgroundPlotter

from scipy.optimize import minimize

from scipy.spatial.transform import Rotation

import matplotlib as mpl

pvd_base='''<?xml version="1.0"?>
<VTKFile type="Collection" version="0.1" byte_order="LittleEndian">
  <Collection>
    <DataSet/>
  </Collection>
</VTKFile>
'''



class MotionCaptureData:

    ### Usage4 결과 저장용
    output_translation_results:list
    output_rotation_euler_rad_results:list
    output_rotation_euler_deg_results:list
    output_rotation_matrix_results:list
    output_frame_list:list
    output_time_list:np.array
    output_df_rigidbody_marker:pd.DataFrame

    # Default
    df_rigidbody: pd.DataFrame
    df_rigidbody_marker: pd.DataFrame
    df_marker: pd.DataFrame
    df_unlabeled: pd.DataFrame
    time_origin_arr: np.array
    time_arr: np.array

    def __init__(self):
        pass

    def add_rigid_angle_euler(self, df):
        # rigidbody에는 quaternion x,y,z,w가 있는데, 이 값을 변환해서 euler angle x,y,z로 변경
        # rigidbody가 몇개?
        #
        no_rigidbody = int(len(self.df_rigidbody.columns)/7)
        euler_columns = ["yaw(Z)", "pitch(Y)", "roll(X)"]
        # 쿼터니언을 Euler ZYX로 변환
        for i in range(0, no_rigidbody):
            quaternion_columns = self.df_rigidbody.iloc[:, i*7:i*7+4].values  # 쿼터니언 데이터 추출
            rotations = Rotation.from_quat(quaternion_columns)  # 쿼터니언을 Rotation 객체로 변환
            euler_angles = rotations.as_euler('zyx', degrees=False)  # Euler ZYX로 변환 (라디안)
            # Euler 각도를 새로운 컬럼에 추가
            for j, col_name in enumerate(euler_columns):
                self.df_rigidbody[f"{col_name}_{i+1}"] = euler_angles[:, j]
                #end for
            #end for
        #end def

    def load_csv(self,
                 file_path: str = r'',
                 b_print: bool = True) :
        """
        4번줄: marker name 확인.

        Type: Rigid Body, Rigid Body Marker,
        Name: rigid body name, rigid body name:marker name
                Unlabeled 2366
                TestBox_85:T3

        """
        if b_print:
            print ("### read_motioncapture_csv")

        # CSV 파일 읽기 / met 정보 확인용
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()
        # lines 2, 3, 4, 5
        # 2: Type
        # 3: Name
        # 5: Parent
        # 6: Rotation or Position
        # 7: X, Y, Z, W, X, Y, Z
        type_arr = np.array(lines[2].replace("\n", "").split(","), dtype=str)[1:]
        name_arr = np.array(lines[3].replace("\n", "").split(","), dtype=str)[1:]
        var_arr  = np.array(lines[7].replace("\n", "").split(","), dtype=str)[1:]

        a1 = type_arr == 'Rigid Body'
        a2 = type_arr == 'Rigid Body Marker'
        # 'Marker' 수정: a3 정의 누락 수정
        a3 = type_arr == 'Marker'
        a4 = type_arr == 'Unlabeled'

        c1 = name_arr[a1]    # Rigid Body로 되어 있는 Column index array
        c2 = name_arr[a2]    # ~
        c3 = name_arr[a3]    # ~
        c4 = name_arr[a4]    # ~

        col_names = np.char.add(np.char.add(name_arr, "::"), var_arr)

        # CSV 파일 읽기
        df = pd.read_csv(file_path, skiprows=7)
        df = df.set_index("Frame")
        # 데이터 확인
        if b_print:
            print(df.head())
        self.time_origin_arr = time_index_arr_o = df.iloc[:, 0].values
        print (self.time_origin_arr)
        # time data 중에서 처음으로 nan_index가 나타나는 index까지를 기본적으로 사용하자.
        nn = np.isnan(time_index_arr_o)
        if nn.any() :
            time_nan_index = np.where(np.isnan(time_index_arr_o))[0][0]
            self.time_arr = time_index_arr = time_index_arr_o[:time_nan_index]
        else:
            time_nan_index = len(time_index_arr_o)
            self.time_arr = time_index_arr = time_index_arr_o
        #
        df = df.iloc[:time_nan_index, :]
        #
        self.df_rigidbody = df.copy(deep=True).iloc[:, a1]
        self.df_rigidbody.index = time_index_arr
        self.df_rigidbody.columns = col_names[a1]
        #
        self.df_rigidbody_marker = df.copy(deep=True).iloc[:, a2]
        self.df_rigidbody_marker.index = time_index_arr
        self.df_rigidbody_marker.columns = col_names[a2]
        #
        self.df_marker = df.copy(deep=True).iloc[:, a3]
        self.df_marker.index = time_index_arr
        self.df_marker.columns = col_names[a3]
        #
        self.df_unlabeled = df.copy(deep=True).iloc[:, a4]
        self.df_unlabeled.index = time_index_arr
        self.df_unlabeled.columns = col_names[a4]
        #
        if b_print:
            print (f"   ... Column Names: {df.columns}")

        #end def

class PointMotionFields:
    """
    RigidBox로 가정하였을 때, 중심 회전-병진에 따른 각 모서리의 위치, 변위, 속도, 가속도를 계산하여
    frame 별로 저장한다.
    """
    output_position_x_list:list
    output_position_y_list:list
    output_position_z_list:list
    output_position_r_list:list

    output_displacement_x_list:list
    output_displacement_y_list:list
    output_displacement_z_list:list
    output_displacement_r_list:list

    output_velocity_x_list:list
    output_velocity_y_list:list
    output_velocity_z_list:list
    output_velocity_r_list:list

    output_df_position:pd.DataFrame
    output_df_displacement:pd.DataFrame
    output_df_velocity:pd.DataFrame

    def __init__(self,
                 mcd:MotionCaptureData, # 회전, 병진 변환 결과를 가지고 있다.
        ):
        self.mcd = mcd
        #end def
    def get_points_by_box(self,
                          box_dimensions:list, # (w, h, d)
                          center:list=(0,0,0),
                          ):
        """
        self.get_points_by_box( box_dimensions = (1000, 100, 40),  center = (0, 0, 0) )
        """
        w, h, d = box_dimensions
        cube = pv.Box(bounds=[
                center[0] - w/2, center[0] + w/2,
                center[1] - h/2, center[1] + h/2,
                center[2] - d/2, center[2] + d/2
                ])
        points = cube.points
        return points
        #end def
    def _create_points_value_dataframe(self, point_list_values, frame_list):
        """
        from CODE.i
        a는 n개의 3d point 좌표의 리스트를 시간별로 저장된 내용이다. a[0]는 0초, a[1]은 1초다.
        pandas dataframe을 만든다.
        dataframe의 index는 frame_list를 별도로 제공한다.
        dataframe의 column은 n개의 3d points로 각각 v1_x, v1_y, v1_z. v2_x, v2_y, v2_z, v3_x, v3_y, v3_z, ...  와 같이 연속적으로 구성하고 각 행은 해당 frame에 대해서 column 값을 각각 부여하는 코드.
        """
        a = point_list_values
        # 각 프레임의 점 개수 확인
        n_points = len(a[0])

        # 열 이름 생성
        columns = []
        for i in range(n_points):
            columns.extend([f'v{i+1}_x', f'v{i+1}_y', f'v{i+1}_z'])
        #
        # 데이터 준비
        data = []
        for frame, points in zip(frame_list, a):
            row = {}
            for idx, (x, y, z) in enumerate(points):
                row[f'v{idx+1}_x'] = x
                row[f'v{idx+1}_y'] = y
                row[f'v{idx+1}_z'] = z
            data.append(row)
        #
        # DataFrame 생성
        df = pd.DataFrame(data, index=frame_list, columns=columns)
        return df
    #
    def calc(self, points:np.array):
        """

        """
        mcd = self.mcd
        #1. mcd frames
        positon_list = []   # frame별로 points들에 대한 회전 - 병진 변환한 위치
        for idx, frame_time in enumerate(mcd.output_frame_list):
            rot_matrix = np.array(mcd.output_rotation_matrix_results[idx])
            tra_vector = np.array(mcd.output_translation_results[idx])

            rotated = np.dot(points, rot_matrix.T)
            positon = rotated + tra_vector
            positon_list.append(positon)
            #end for
        #2. position의 변화를 displacement_list에 저장
        displacement_list = []
        for idx, frame_time in enumerate(mcd.output_frame_list):
            if idx == 0:
                before_position = positon_list[idx]
                displacement_list.append(before_position-before_position)
                continue
            current_position = positon_list[idx]
            disp = current_position - before_position
            displacement_list.append(disp)
            #end for
        #3. velocity
        velocity_list = []
        before_time = 0.0
        for idx, frame_time in enumerate(mcd.output_time_list):
            current_time = frame_time
            if idx == 0:
                before_position = positon_list[idx]
                velocity_list.append( before_position - before_position)
                before_time = frame_time
                continue
            current_position = positon_list[idx]
            vel = (current_position - before_position) / (current_time - before_time)
            velocity_list.append(vel)
            before_position = current_position
            before_time = current_time
            #end for

        self.output_position_list = positon_list
        self.output_position_x_list = [[v[0] for v in fv] for fv in positon_list]
        self.output_position_y_list = [[v[1] for v in fv] for fv in positon_list]
        self.output_position_z_list = [[v[2] for v in fv] for fv in positon_list]

        self.output_displacement_list = displacement_list
        self.output_displacement_x_list = [[v[0] for v in fv] for fv in displacement_list]
        self.output_displacement_y_list = [[v[1] for v in fv] for fv in displacement_list]
        self.output_displacement_z_list = [[v[2] for v in fv] for fv in displacement_list]
        self.output_displacement_r_list = [[np.sqrt(v[0]**2 + v[1]**2+ v[2]**2) for v in fv] for fv in displacement_list]

        self.output_velocity_list = velocity_list
        self.output_velocity_x_list = [[v[0] for v in fv] for fv in velocity_list]
        self.output_velocity_y_list = [[v[1] for v in fv] for fv in velocity_list]
        self.output_velocity_z_list = [[v[2] for v in fv] for fv in velocity_list]
        self.output_velocity_r_list = [[ np.sqrt(v[0]**2 + v[1]**2+ v[2]**2) for v in fv] for fv in velocity_list ]

        # dataframe
        self.output_df_position = self._create_points_value_dataframe(point_list_values=positon_list, frame_list=mcd.output_time_list)
        self.output_df_displacement = self._create_points_value_dataframe(point_list_values=displacement_list, frame_list=mcd.output_time_list)
        self.output_df_velocity = self._create_points_value_dataframe(point_list_values=velocity_list, frame_list=mcd.output_time_list)
        #end def

    def rot(self):
        import numpy as np
        from scipy.spatial.transform import Rotation

        # 가상의 시간 데이터 (단위: 초)
        # 예: 0초, 0.1초, 0.2초, ...
        times = np.array([0.0, 0.1, 0.2, 0.3, 0.4, 0.5])

        # 가상의 회전 행렬 시퀀스 (shape: (N, 3, 3))
        # N은 시간 스텝 수입니다.
        # 이 예제에서는 Z축으로 일정한 각속도로 회전하는 상황을 가정합니다.
        angular_speed_z = 1.0 # rad/s
        rotation_matrices = []
        for t in times:
            # Z축을 중심으로 t * angular_speed_z 라디안 회전하는 회전 행렬 생성
            # 실제 데이터에서는 측정된 회전 행렬을 사용합니다.
            r = Rotation.from_rotvec([0, 0, angular_speed_z * t])
            rotation_matrices.append(r.as_matrix())

        # 리스트를 numpy 배열로 변환
        rotation_matrices = np.array(rotation_matrices)

        print("시간에 따른 회전 행렬 시퀀스 (예시):")
        for i, R in enumerate(rotation_matrices):
            print(f"시간 {times[i]}초:\n{R}\n")

        # scipy.spatial.transform.Rotation 객체 생성
        # from_matrix 메서드를 사용하여 회전 행렬 시퀀스로부터 Rotation 객체 생성
        rotations = Rotation.from_matrix(rotation_matrices)

        # compute_angular_velocity 메서드를 사용하여 각속도 계산
        # 이 메서드는 인접한 회전 간의 각속도를 계산합니다.
        # 결과는 각 시간 스텝 사이의 평균 각속도를 나타냅니다.
        # 반환되는 각속도의 shape는 (N-1, 3) 입니다.
        # 여기서 3은 [omega_x, omega_y, omega_z] 성분입니다.
        angular_velocities = rotations.compute_angular_velocity(times)

        print("\n계산된 각속도 벡터 [omega_x, omega_y, omega_z] (글로벌 좌표계 기준):")
        # compute_angular_velocity는 기본적으로 각 시간 간격의 중간 시점에 대한 각속도를 반환합니다.
        # 따라서 결과 배열의 길이는 시간 스텝 수보다 1 작습니다.
        for i in range(len(times) - 1):
            # 각속도는 i번째 시간과 i+1번째 시간 사이의 회전을 기반으로 계산됩니다.
            # 정확한 시점은 (times[i] + times[i+1]) / 2 로 볼 수 있습니다.
            print(f"시간 {times[i]:.1f} ~ {times[i+1]:.1f} 사이: {angular_velocities[i]} rad/s")

        # 결과는 각 간격의 평균 각속도입니다.
        # 이 예시에서는 Z축 각속도가 1.0으로 일정하므로, 결과도 [0, 0, 1.0] 근처 값이 나옵니다.

        #end def
    #end class

def get_box_edge_info(box_vertices):
    """
    직육면체 모서리점으로부터 12개 모서리의 중앙 좌표와 라벨을 계산합니다.

    Args:
        box_vertices (np.ndarray): 직육면체의 8개 모서리점 (8x3 형태).

    Returns:
        tuple: (edge_midpoints (np.ndarray), edge_labels (list)).
               유효하지 않은 입력 시 (None, None).
    """
    if box_vertices is None or box_vertices.shape != (8, 3):
        print("Error: 유효한 직육면체 모서리점(8x3 배열)이 제공되지 않았습니다.")
        return None, None

    edges_indices = [
        (0, 4), (1, 5), (2, 6), (3, 7), # Edges along X-axis (E1-E4)
        (0, 2), (1, 3), (4, 6), (5, 7), # Edges along Y-axis (E5-E8)
        (0, 1), (2, 3), (4, 5), (6, 7)  # Edges along Z-axis (E9-E12)
    ]
    edge_labels = [f'E{i+1}' for i in range(12)]
    edge_midpoints = np.array([(box_vertices[start] + box_vertices[end]) / 2.0 for start, end in edges_indices])

    return edge_midpoints, edge_labels

def get_box_face_info(box_vertices):
    """
    직육면체 모서리점으로부터 6개 면의 중심 좌표와 라벨을 계산합니다.

    Args:
        box_vertices (np.ndarray): 직육면체의 8개 모서리점 (8x3 형태).

    Returns:
        tuple: (face_centroids (np.ndarray), face_labels (list)).
               유효하지 않은 입력 시 (None, None).
    """
    if box_vertices is None or box_vertices.shape != (8, 3):
        print("Error: 유효한 직육면체 모서리점(8x3 배열)이 제공되지 않았습니다.")
        return None, None

    faces_indices = [
        (0, 4, 6, 2), # -Z face (F1)
        (1, 5, 7, 3), # +Z face (F2)
        (0, 4, 5, 1), # -Y face (F3)
        (2, 6, 7, 3), # +Y face (F4)
        (0, 2, 3, 1), # -X face (F5)
        (4, 6, 7, 5)  # +X face (F6)
    ]
    face_labels = [f'F{i+1}' for i in range(6)]
    face_centroids = np.array([np.mean(box_vertices[list(indices)], axis=0) for indices in faces_indices])

    return face_centroids, face_labels

def get_box_vertex_info(box_vertices):
    """
    직육면체 모서리점으로부터 8개 꼭지점의 좌표와 라벨을 계산합니다.

    Args:
        box_vertices (np.ndarray): 직육면체의 8개 모서리점 (8x3 형태).

    Returns:
        tuple: (vertex_coords (np.ndarray), vertex_labels (list)).
               유효하지 않은 입력 시 (None, None).
    """
    if box_vertices is None or box_vertices.shape != (8, 3):
        print("Error: 유효한 직육면체 모서리점(8x3 배열)이 제공되지 않았습니다.")
        return None, None

    vertex_coords = np.array(box_vertices) # 꼭지점 좌표는 이미 box_vertices에 있습니다.
    vertex_labels = [f'V{i+1}' for i in range(8)]

    return vertex_coords, vertex_labels

def quaternion_to_euler_zyx(quaternion, degrees=True):
    """
    Convert a quaternion to Euler ZYX (yaw, pitch, roll) angles.

    Parameters:
        quaternion (list or np.ndarray): Quaternion [x, y, z, w].
        degrees (bool): If True, return angles in degrees. Otherwise, return in radians.

    Returns:
        np.ndarray: Euler angles [yaw (Z), pitch (Y), roll (X)] in ZYX order.
    """
    try:
        # Create a Rotation object from the quaternion
        rotation = Rotation.from_quat(quaternion)

        # Convert to Euler angles in ZYX order
        euler_angles = rotation.as_euler('zyx', degrees=degrees)
        return euler_angles
    except Exception as e:
        print(f"Error converting quaternion to Euler ZYX: {e}")
        return None

# 회전 행렬을 오일러 각도로 변환하는 함수
def rotation_matrix_to_euler_angles(rotation_matrix, convention='zyx', degrees=True):
    """ 3x3 회전 행렬을 오일러 각도로 변환합니다. """
    """ 안정성을 높이기 위해서 강제로 quaternion 변환 후 다시 오일러 변환하는 방식을 취하자."""
    try:
        det = np.linalg.det(rotation_matrix)
        if det < 0:
            # 세 번째 열의 부호를 반전시켜 오른손 좌표계로 변환
            rotation_matrix[:, 2] *= -1

        r = Rotation.from_matrix(rotation_matrix)
        q = r.as_quat()
        r2 = Rotation.from_quat(q)
        euler_angles = r2.as_euler(convention, degrees=degrees)

        return euler_angles
    except Exception as e:
        print(f"Error converting rotation matrix to Euler angles: {e}")
        # This can happen for improper rotations (reflection) or invalid matrices
        return None

def get_closest_point_on_obb_surface(point, obb_center, obb_rotation_matrix, obb_half_extents):
    """
    Find the closest point on the surface of an Oriented Bounding Box (OBB) to a given point.

    Parameters:
        point (numpy.ndarray): The 3D point (1x3).
        obb_center (numpy.ndarray): The center of the OBB (1x3).
        obb_rotation_matrix (numpy.ndarray): The 3x3 rotation matrix of the OBB.
        obb_half_extents (numpy.ndarray): The half extents of the OBB along each axis (1x3).

    Returns:
        numpy.ndarray: The closest point on the OBB surface in world coordinates.
    """
    # Transform the point to the OBB's local coordinate system
    point_local = obb_rotation_matrix.T @ (point - obb_center)

    # Clamp the point to the OBB's extents
    closest_local = np.clip(point_local, -obb_half_extents, obb_half_extents)

    # Transform the clamped point back to world coordinates
    closest_world = obb_rotation_matrix @ closest_local + obb_center
    return closest_world


def align_points_svd(source_points, target_points):
    """
    Compute the optimal rigid transformation (rotation + translation) to align source points to target points using SVD.

    Parameters:
        source_points (numpy.ndarray): Source points (Nx3).
        target_points (numpy.ndarray): Target points (Nx3).

    Returns:
        tuple: Rotation matrix (3x3) and translation vector (1x3).
    """
    num_points = source_points.shape[0]
    if num_points != target_points.shape[0]:
        raise ValueError("source_points and target_points must have the same number of points.")
    if num_points < 3:
        print("Warning: At least 3 points are recommended for SVD alignment.")
        if num_points == 1:
            return np.eye(3), target_points[0] - source_points[0]
        return np.eye(3), np.zeros(3)

    # Compute centroids
    centroid_source = np.mean(source_points, axis=0)
    centroid_target = np.mean(target_points, axis=0)

    # Center the points
    centered_source = source_points - centroid_source
    centered_target = target_points - centroid_target

    # Compute the covariance matrix
    H = centered_source.T @ centered_target

    # Perform Singular Value Decomposition (SVD)
    U, _, Vh = np.linalg.svd(H)
    V = Vh.T
    R = V @ U.T

    # Ensure a proper rotation (det(R) = 1)
    if np.linalg.det(R) < 0:
        V[:, -1] *= -1
        R = V @ U.T

    # Compute the translation
    t = centroid_target - R @ centroid_source
    return R, t

def get_canonical_box_vertices(half_extents):
    """
    Generate the 8 corner vertices of an axis-aligned box centered at the origin.

    Parameters:
        half_extents (numpy.ndarray): Half extents of the box along each axis (1x3).

    Returns:
        numpy.ndarray: Array of 8 vertices (8x3).
    """
    hx, hy, hz = half_extents
    vertices = [
        [-hx, -hy, -hz],  # 0
        [-hx, -hy, +hz],  # 1
        [-hx, +hy, -hz],  # 2
        [-hx, +hy, +hz],  # 3
        [+hx, -hy, -hz],  # 4
        [+hx, -hy, +hz],  # 5
        [+hx, +hy, -hz],  # 6
        [+hx, +hy, +hz],  # 7
    ]
    return np.array(vertices)


def fit_oriented_box_to_surface(points, box_dimensions, max_iterations=1500, tolerance=1e-12, point_on_face_pairs=None, ref_center=None, ref_rotation_matrix=None, ):
    """
    Fit an Oriented Bounding Box (OBB) of fixed dimensions to a set of 3D points.

    Parameters:
        points (numpy.ndarray): Nx3 array of 3D points.
        box_dimensions (list): Dimensions of the box [length, width, height].
        max_iterations (int): Maximum number of iterations for fitting.
        tolerance (float): Convergence tolerance for the transformation change.
        point_on_face_pairs (list): List of tuples [(point_index, face_index, distance), ...] specifying constraints.

    Returns:
        tuple: Final vertices of the fitted box (8x3), rotation matrix (3x3), and center (1x3).
    """
    if not isinstance(points, np.ndarray) or points.ndim != 2 or points.shape[1] != 3 or points.shape[0] < 1:
        print("Error: points must be an Nx3 numpy array with at least one point.")
        return None, None, None

    # Remove rows with NaN values
    try:
        # Ensure the input is a numpy array of floats
        points = np.asarray(points, dtype=np.float64)
        points = points[~np.isnan(points).any(axis=1)]
    except ValueError as e:
        print(f"Error: Unable to convert points to a numeric array. {e}")
        return None, None, None

    if points.shape[0] < 3:
        print(f"Warning: OBB fitting is recommended for at least 3 points. Current points: {points.shape[0]}")
        return None, None, None

    # Initialize the box parameters
    points = np.asarray(points, dtype=np.float64)
    box_half_extents = np.asarray(box_dimensions, dtype=np.float64) / 2.0
    current_center = np.mean(points, axis=0)
    if ref_center is not None:
        current_center = ref_center

    # Compute the initial rotation matrix using PCA
    centered_points = points - current_center
    if ref_rotation_matrix is not None:
        initial_rotation_matrix = ref_rotation_matrix
    else:
        try:
            covariance_matrix = np.cov(centered_points.T)
            eigenvalues, eigenvectors = np.linalg.eigh(covariance_matrix)
            sorted_indices = np.argsort(eigenvalues)[::-1]
            initial_rotation_matrix = eigenvectors[:, sorted_indices]
        except np.linalg.LinAlgError:
            print("Warning: Covariance matrix computation failed. Using identity matrix for initial rotation.")
            initial_rotation_matrix = np.eye(3)

    current_rotation_matrix = initial_rotation_matrix

    print(f"Starting OBB fitting (max {max_iterations} iterations, tolerance {tolerance:.1e})")
    for i in range(max_iterations):
        # Find the closest points on the OBB surface
        closest_points_on_obb = []
        for idx, point in enumerate(points):
            if point_on_face_pairs and any(pair[0] == idx for pair in point_on_face_pairs):
                # If the point is constrained to a specific face
                face_index = next(pair[1] for pair in point_on_face_pairs if pair[0] == idx)
                closest_point = get_closest_point_on_specific_face(
                    point, current_center, current_rotation_matrix, box_half_extents, face_index
                )
            else:
                # General case: closest point on any OBB surface
                closest_point = get_closest_point_on_obb_surface(
                    point, current_center, current_rotation_matrix, box_half_extents
                )
            closest_points_on_obb.append(closest_point)
        closest_points_on_obb = np.array(closest_points_on_obb)

        # Compute the optimal rigid transformation
        R_step, t_step = align_points_svd(closest_points_on_obb, points)

        # Check for convergence
        rotation_change = np.linalg.norm(R_step - np.eye(3))
        translation_change = np.linalg.norm(t_step)
        transform_change = rotation_change + translation_change
        if transform_change < tolerance:
            print(f"Converged after {i + 1} iterations (change: {transform_change:.6e})")
            break

        # Update the center and rotation matrix
        current_center = R_step @ current_center + t_step
        current_rotation_matrix = R_step @ current_rotation_matrix

    if i == max_iterations - 1 and transform_change >= tolerance:
        print(f"Warning: Maximum iterations reached without convergence (final change: {transform_change:.6e}).")

    # Compute the final box vertices
    canonical_vertices = get_canonical_box_vertices(box_half_extents)
    final_vertices = (current_rotation_matrix @ canonical_vertices.T).T + current_center
    return final_vertices, current_rotation_matrix, current_center


def get_closest_point_on_specific_face(point, obb_center, obb_rotation_matrix, obb_half_extents, face_index):
    """
    Find the closest point on a specific face of an Oriented Bounding Box (OBB).

    Parameters:
        point (numpy.ndarray): The 3D point (1x3).
        obb_center (numpy.ndarray): The center of the OBB (1x3).
        obb_rotation_matrix (numpy.ndarray): The 3x3 rotation matrix of the OBB.
        obb_half_extents (numpy.ndarray): The half extents of the OBB along each axis (1x3).
        face_index (int): The index of the face (0 to 5).

    Returns:
        numpy.ndarray: The closest point on the specified face in world coordinates.
    """
    # Transform the point to the OBB's local coordinate system
    point_local = obb_rotation_matrix.T @ (point - obb_center)

    # Clamp the point to the extents of the specific face
    if face_index == 0:  # -Z face
        point_local[2] = -obb_half_extents[2]
    elif face_index == 1:  # +Z face
        point_local[2] = obb_half_extents[2]
    elif face_index == 2:  # -Y face
        point_local[1] = -obb_half_extents[1]
    elif face_index == 3:  # +Y face
        point_local[1] = obb_half_extents[1]
    elif face_index == 4:  # -X face
        point_local[0] = -obb_half_extents[0]
    elif face_index == 5:  # +X face
        point_local[0] = obb_half_extents[0]

    # Clamp the other two coordinates to the box extents
    point_local = np.clip(point_local, -obb_half_extents, obb_half_extents)

    # Transform the clamped point back to world coordinates
    closest_world = obb_rotation_matrix @ point_local + obb_center
    return closest_world


# 직사각형 메쉬 생성 및 VTK 저장 함수
def create_rectangular_mesh(box_size_lwh, elem_nums,
                            translation=(0, 0, 0),
                            rotation=None,
                            rotation_matrix=None,
                            output_file:str=None):
    """
    Create a rectangular mesh with given dimensions, element counts, translation, and rotation, and save as a VTK file.
    Additionally, add a vtkCubeSource with the same transformation.

    Parameters:
        box_size_lwh (list): Dimensions of the rectangle [length (x), width (y), height (z)].
        elem_nums (list): Number of elements along each axis [x, y, z].
        translation (tuple): Translation in x, y, z directions.
        rotation (tuple): Rotation in z, y, x Euler angles (radian, ZYX order).
        output_file (str): Output VTK file name.
    """
    l, w, h = box_size_lwh  # Unpack box dimensions
    n_m_l, n_m_w, n_m_h = elem_nums  # Unpack element counts

    # Generate grid points
    x = np.linspace(-l / 2, l / 2, n_m_l + 1)
    y = np.linspace(-w / 2, w / 2, n_m_w + 1)
    z = np.linspace(-h / 2, h / 2, n_m_h + 1)
    points = np.array([[xi, yi, zi] for zi in z for yi in y for xi in x])

    # Apply translation and rotation to the points
    '''
    euler_angles = rotation
    rot = Rotation.from_euler('zyx', euler_angles, degrees=False)
    rotation_matrix = rot.as_matrix()
    points = (rotation_matrix @ points.T).T + translation
    '''
    # XZ Plane
    vtk_xz_plane = vtk.vtkPlaneSource()
    vtk_xz_plane.SetOrigin( -2000., 0., -2000.)
    vtk_xz_plane.SetPoint1(  2000., 0., -2000.)
    vtk_xz_plane.SetPoint2( -2000., 0.,  2000.)
    vtk_xz_plane.SetResolution(2,2)
    vtk_xz_plane.Update()

    # Create VTK points
    vtk_points = vtk.vtkPoints()
    for point in points:
        vtk_points.InsertNextPoint(point)

    # Generate cells (quads) for each face
    quads = vtk.vtkCellArray()
    face_labels = vtk.vtkStringArray()
    face_labels.SetName("FaceLabels")
    #
    # Bottom and top faces (z constant)
    for k, label in zip([0, n_m_h], ["F1", "F2"]):  # Bottom face (z=0), Top face (z=h)
        for j in range(n_m_w):
            for i in range(n_m_l):
                quad = vtk.vtkQuad()
                idx = lambda i, j, k: i + j * (n_m_l + 1) + k * (n_m_l + 1) * (n_m_w + 1)
                quad.GetPointIds().SetId(0, idx(i, j, k))
                quad.GetPointIds().SetId(1, idx(i + 1, j, k))
                quad.GetPointIds().SetId(2, idx(i + 1, j + 1, k))
                quad.GetPointIds().SetId(3, idx(i, j + 1, k))
                quads.InsertNextCell(quad)
        face_labels.InsertNextValue(label)

    # Front and back faces (y constant)
    for j, label in zip([0, n_m_w], ["F3", "F4"]):  # Front face (y=0), Back face (y=w)
        for k in range(n_m_h):
            for i in range(n_m_l):
                quad = vtk.vtkQuad()
                idx = lambda i, j, k: i + j * (n_m_l + 1) + k * (n_m_l + 1) * (n_m_w + 1)
                quad.GetPointIds().SetId(0, idx(i, j, k))
                quad.GetPointIds().SetId(1, idx(i + 1, j, k))
                quad.GetPointIds().SetId(2, idx(i + 1, j, k + 1))
                quad.GetPointIds().SetId(3, idx(i, j, k + 1))
                quads.InsertNextCell(quad)
        face_labels.InsertNextValue(label)

    # Left and right faces (x constant)
    for i, label in zip([0, n_m_l], ["F5", "F6"]):  # Left face (x=0), Right face (x=l)
        for k in range(n_m_h):
            for j in range(n_m_w):
                quad = vtk.vtkQuad()
                idx = lambda i, j, k: i + j * (n_m_l + 1) + k * (n_m_l + 1) * (n_m_w + 1)
                quad.GetPointIds().SetId(0, idx(i, j, k))
                quad.GetPointIds().SetId(1, idx(i, j + 1, k))
                quad.GetPointIds().SetId(2, idx(i, j + 1, k + 1))
                quad.GetPointIds().SetId(3, idx(i, j, k + 1))
                quads.InsertNextCell(quad)
        face_labels.InsertNextValue(label)
    # Apply translation and rotation to the cube using vtkTransform
    # 회전 순서는 반대다.. ZYX
    transform = vtk.vtkTransform()
    #transform.Translate(*translation)
    '''
    transform.RotateX(np.degrees(rotation[0]))
    transform.RotateY(np.degrees(rotation[1]))
    transform.RotateZ(np.degrees(rotation[2]))
    '''
    #'''
    #transform.RotateX(90)
    #transform.RotateZ(np.degrees(rotation[2]))
    #transform.RotateY(np.degrees(rotation[1]))
    #'''
    #
    if rotation_matrix is not None:
        vtk_matrix = vtk.vtkMatrix4x4()
        # 회전 행렬 적용
        for i in range(3):
            for j in range(3):
                vtk_matrix.SetElement(i, j, rotation_matrix[i, j])
        # 변위 적용 (4x4 행렬의 마지막 열)
        for i in range(3):
            vtk_matrix.SetElement(i, 3, translation[i])
        # vtkTransform 생성 및 변환 행렬 적용
        transform = vtk.vtkTransform()
        transform.SetMatrix(vtk_matrix)
        transform.GetOrientation()
        #end if
    #
    # Create a VTK PolyData object for the mesh
    polydata = vtk.vtkPolyData()
    polydata.SetPoints(vtk_points)
    polydata.SetPolys(quads)
    polydata.GetCellData().AddArray(face_labels)
    # Create a vtkCubeSource for the cube
    cube = vtk.vtkCubeSource()
    cube.SetXLength(l)
    cube.SetYLength(w)
    cube.SetZLength(h)
    cube.SetCenter(0, 0, 0)  # Center the cube at the origin

    transform_filter = vtk.vtkTransformPolyDataFilter()
    transform_filter.SetTransform(transform)
    transform_filter.SetInputData(polydata)
    transform_filter.Update()

    transform_filter2 = vtk.vtkTransformPolyDataFilter()
    transform_filter2.SetTransform(transform)
    transform_filter2.SetInputConnection(cube.GetOutputPort())
    transform_filter2.Update()

    # Combine the mesh and the cube using vtkAppendPolyData
    append_filter = vtk.vtkAppendPolyData()
    # mesh | mesh 정보 추가 시 아래 주석 해제
    #append_filter.AddInputData(transform_filter.GetOutput())
    #append_filter.AddInputData(polydata)

    # plane
    append_filter.AddInputConnection(vtk_xz_plane.GetOutputPort())

    # cube
    append_filter.AddInputData(transform_filter2.GetOutput())
    #append_filter.AddInputData(vtk_xz_plane.GetOutput())

    # center sphere
    #sphere = pv.Sphere(center=(0, 0, 0), radius=50)  # 반지름 50, 원점 중심
    #sphere_vtk = sphere.to_vtk()
    #append_filter.AddInputData(sphere_vtk)

    # update
    append_filter.Update()

    # Write the combined data to a VTK file
    #writer = vtk.vtkPolyDataWriter()
    #writer.SetFileName(output_file)
    #writer.SetInputData(append_filter.GetOutput())
    #writer.Write()
    if output_file.endswith(".vtp"):
        writer = vtk.vtkXMLPolyDataWriter()
    elif output_file.endswith(".vtk"):
        writer = vtk.vtkPolyDataWriter()
    writer.SetFileName(output_file)
    writer.SetInputData(append_filter.GetOutput())
    writer.Write()

    print(f"Rectangular mesh with cube saved to {output_file}")

# PyVista로 VTK 파일 시각화 함수
def visualize_vtk_file( vtk_file=None,
                        points=None,
                        box_vertices=None,
                        text_label_font_size=10,
                        vertex_label_offset=(-1, -1, -1),
                       ):
    """
    Visualize a VTK file using PyVista with XYZ axes at (0, 0, 0) and face labels.

    Parameters:
        vtk_file (str): Path to the VTK file.
        points (numpy.ndarray): Optional. Points to visualize alongside the mesh.
    """
    # Create a PyVista plotter
    plotter = pv.Plotter()
    #plotter = BackgroundPlotter()  # qt UI
    #plotter.add_orientation_widget()
    plotter.add_axes()

    def align_xy_view():
        plotter.view_xy()
        plotter.render()
    def align_yz_view():
        plotter.view_yz()
        plotter.render()
    def align_zx_view():
        plotter.view_zx()
        plotter.render()

    plotter.add_key_event("1", lambda: align_xy_view())
    plotter.add_key_event("2", lambda: align_yz_view())
    plotter.add_key_event("3", lambda: align_zx_view())

    # Orthographic View 설정
    #plotter.camera.parallel_projection = True
    # Add an XZ plane at Y=0
    xz_plane = pv.Plane(center=(0, 0, 0), direction=(0, 1, 0), i_size=5000, j_size=5000)
    plotter.add_mesh(xz_plane, color="lightgray", opacity=0.5, label='XZ Plane')

    pv.global_theme.allow_empty_mesh = True
    if vtk_file is not None and isinstance(vtk_file, str):
        # Load the VTK file
        mesh = pv.read(vtk_file)
        # Add the mesh
        plotter.add_mesh(mesh, color="lightblue", show_edges=True, opacity=0.8, label='Generated Mesh')

    # Customize axes style

    # Add original points with different colors and legend
    if points is not None and isinstance(points, np.ndarray) and points.shape[0] > 0:
        # Define colors for points
        cmap = mpl.colormaps['tab10']
        colors_rgb255_list = [(np.array(cmap(i)[:3]) * 255).astype(int).tolist() for i in np.linspace(0, 1, points.shape[0])]
        point_labels = [f'P{i+1}' for i in range(points.shape[0])]

        # Add points to the plot
        for i in range(points.shape[0]):
            point = points[i, :] + vertex_label_offset
            if np.isnan(np.array(point) ).any():
                continue
            color = colors_rgb255_list[i]
            point_cloud = pv.PolyData([point])
            plotter.add_mesh(point_cloud, color=color, point_size=15, render_points_as_spheres=True, label=f'P{i+1}')

        # Add point labels
        plotter.add_point_labels(points, point_labels, always_visible=True, font_size=10, shape_color='white', shape_opacity=0.0)

    # Add the fitted box if available
    if box_vertices is not None and isinstance(box_vertices, np.ndarray) and box_vertices.shape == (8, 3):

        # Define the 12 edges of the box using vertex indices (0-based) for plotting lines
        edge_lines_indices = np.array([
            [0, 1], [0, 2], [0, 4],
            [1, 3], [1, 5],
            [2, 3], [2, 6],
            [3, 7],
            [4, 5], [4, 6],
            [5, 7],
            [6, 7]
        ])

        # Create a PolyData object for the edges
        lines = np.hstack((np.full((edge_lines_indices.shape[0], 1), 2), edge_lines_indices)).flatten()
        # Create PolyData from vertices and lines
        box_polydata = pv.PolyData(box_vertices, lines=lines)
        # Add the box edges to the plotter
        plotter.add_mesh(box_polydata, color='blue', line_width=3, label='Fitted Box Edges')

        # Add edge labels
        edge_midpoints, edge_labels = get_box_edge_info(box_vertices)
        if edge_midpoints is not None and edge_labels is not None:
            plotter.add_point_labels(edge_midpoints, edge_labels, always_visible=True, text_color='purple',
                                 font_size=text_label_font_size, shape_color='white',)
        # Add face labels
        face_centroids, face_labels = get_box_face_info(box_vertices)
        if face_centroids is not None and face_labels is not None:
            plotter.add_point_labels(face_centroids, face_labels, always_visible=True, text_color='blue',
                                 font_size=text_label_font_size, shape_color='white',)

        # Add vertex labels (V1-V8)
        vertex_coords, vertex_labels = get_box_vertex_info(box_vertices)
        if vertex_coords is not None and vertex_labels is not None:
            plotter.add_point_labels(vertex_coords, vertex_labels, always_visible=True, text_color='green',
                                 font_size=text_label_font_size, shape_color='white',)


    # Show the plot
    plotter.show()
###
def rigid_box_animation(box_dimensions:list,
                        mcd:MotionCaptureData,
                        pmf:PointMotionFields,
                        ):
    '''
    rigid_box_animation(box_dimensions, mcd)
    속도, 변위, 위치 등의 field 출력
    '''
    ### mcd로 부터 필요한 정보를 먼저 확보

    time_list:list = mcd.output_frame_list
    box_translation_list:list = mcd.output_translation_results
    box_rotation_euler_deg_list:list = mcd.output_rotation_euler_deg_results
    box_rotation_matrix_list:list = mcd.output_rotation_matrix_results
    marker_df:pd.DataFrame = mcd.output_df_rigidbody_marker  # csv로 부터 읽어들인 marker의 정보들...
    field_name = 'Value'
    pl:pv.Plotter = pv.Plotter()
    #pl = BackgroundPlotter()

    center = [0, 0, 0]
    w, h, d = box_dimensions
    cube = pv.Box(bounds=[
        center[0] - w/2, center[0] + w/2,
        center[1] - h/2, center[1] + h/2,
        center[2] - d/2, center[2] + d/2
        ])

    cube.point_data[field_name] = np.zeros(len(cube.points))
    #cube_actor = pl.add_mesh(cube, color='lightgreen', show_edges=True, name='BOX')
    cube_actor = pl.add_mesh(cube, show_edges=True, name='BOX',
                             scalars=field_name,
                             scalar_bar_args={'title': field_name},
                             )
    frame_text_actor = pl.add_text(
        "Frame: 0",
        position='lower_left',  # 좌측 상단에 표시
        font_size=10,
        color='black',
        name='frame_counter' # 텍스트 액터의 고유 이름 지정
    )

    #
    pl.add_axes()

    xz_plane = pv.Plane(center=(0, 0, 0), direction=(0, 1, 0), i_size=5000, j_size=5000)
    pl.add_mesh(xz_plane, color="lightgray", opacity=0.5, label='XZ Plane')

    # 카메라 위치 설정 (선택 사항)
    #pl.camera_position = [(10.0, 5.0, 5.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0)]

    # 애니메이션 설정 변수
    max_steps = len(box_rotation_matrix_list)  # 애니메이션 총 스텝 수 (프레임 수)
    duration_ms = 2000 # 각 스텝(프레임) 사이의 간격 (밀리초)
    radius = 500.0     # 구체가 움직일 원형 경로의 반지름

    # step 인자는 현재 스텝 번호 (0부터 max_steps-1까지)
    global astep
    astep = 0

    global marker_points_actor_list
    marker_points_actor_list = []

    def marker_points_label(mode, step_idx=0):
        """
        mode=0 : create
        mode=1 : move position
        """
        vertex_label_offset = np.array([-2.,-2.,-2.])
        global marker_points_actor_list

        # Add original points with different colors and legend
        if mode == 0 :
            col_series = marker_df.iloc[0, :]
            marker_points = parse_point_array_internal(col_series.values)
            # Define colors for points
            cmap = mpl.colormaps['tab10']
            colors_rgb255_list = [(np.array(cmap(i)[:3]) * 255).astype(int).tolist() for i in np.linspace(0, 1, marker_points.shape[0])]
            point_labels = [f'P{i+1}' for i in range(marker_points.shape[0])]

            # Add points to the plot
            for i in range(marker_points.shape[0]):
                point = marker_points[i, :]
                if np.isnan( marker_points ).any():
                    continue
                color = colors_rgb255_list[i]
                point_cloud = pv.PolyData([point])
                p_actor:pv.Actor = pl.add_mesh(mesh=point_cloud, color=color, point_size=12, render_points_as_spheres=True, label=f'P{i+1}')
                #marker_points_actor_list.append(p_actor)
                # Add point labels
                #p_actor = pl.add_point_labels(marker_points, point_labels, always_visible=True, font_size=10, shape_color='white', shape_opacity=0.0)
                marker_points_actor_list.append(p_actor)
                #end for
            #end if
        elif mode == 1:
            col_series_0 = marker_df.iloc[0, :]
            marker_points_0 = parse_point_array_internal(col_series_0.values)
            col_series = marker_df.iloc[step_idx, :]
            marker_points = parse_point_array_internal(col_series.values)
            for i in range(len(marker_points_actor_list)):
                p_actor = marker_points_actor_list[i]
                #print (step_idx, i, marker_points[i, :])
                transform = pv.Transform()
                transform.translate( marker_points[i] - marker_points_0[i])
                p_actor.SetUserTransform(transform)
                # p_actor.transform(trans=transform, inplace=False) # 이 부분은 PyVista 버전에 따라 다를 수 있음
                #end for
            #end if

        #end def
    #
    def callback_update_box(step):
        """
        애니메이션 스텝마다 호출되는 콜백 함수.
        구체의 위치와 회전을 업데이트하고 프레임 텍스트를 업데이트합니다.
        """
        anim(cmd=1, step=step)
        #pl.render()

        #end def

    # add_timer_event를 사용하여 애니메이션 콜백 함수 등록
    # max_steps 동안 duration_ms 간격으로 animation_callback 함수를 호출합니다.
    def start_anim():
        pl.add_timer_event(
            max_steps=max_steps,
            duration=duration_ms,
            callback=callback_update_box,
            )
        #end def
    pl.add_key_event("b", lambda: start_anim())

    def anim(cmd:int, step:int=None,):
        """
        cmd = 1 : prev
        cmd = 2 : next
        """
        global astep
        if step is not None:
            astep = step
        else:
            if cmd == 1:
                astep = astep - 1
            elif cmd == 2:
                astep = astep + 1

            if astep < 0:
                astep = len(box_translation_list)-1
            elif astep > len(box_translation_list)-1:
                astep = 0

        # translate / rotate
        transform = pv.Transform()
        transform.rotate(box_rotation_matrix_list[astep])
        transform.translate(box_translation_list[astep])
        #vv = cube_actor.transform(trans=transform, inplace=False)
        cube_actor.SetUserTransform(transform)
        #
        frame_text_actor.SetText(0,f"Frame: {astep}")
        ### Markers
        marker_points_label(mode=1, step_idx=astep)
        ### point values
        new_scalars = [ v for v in pmf.output_velocity_r_list[astep] ]   # cube points에 대한
        cube.point_data[field_name] = new_scalars
        pl.update_scalar_bar_range( ( np.min(new_scalars), np.max(new_scalars) ), field_name)

        pl.render()
        #end def
    pl.add_key_event("n", lambda: anim(1))
    pl.add_key_event("m", lambda: anim(2))

    #if pl.interactor is not None:
    #    pl.interactor.Initialize()


    # Plotter 창을 표시하고 애니메이션 시작

    # marker 초기 생성
    marker_points_label(mode=0)
    callback_update_box(step=0)
    #
    pl.iren.initialize()
    pl.show()
    #pl.app.exec_() # pyvista qt, https://qtdocs.pyvista.org/usage.html
    '''
    pl.open_movie('test.mp4')
    pl.show(auto_close=False)
    pl.write_frame()    # write initial data
    for i in range(len(box_translation_list)):
        x, y, z = box_translation_list[i]
        cube_actor.position = [x, y, z]
        pl.write_frame()  # Write this frame
    pl.close()
    '''
    return
# 직육면체와 점들 간의 최적 변환을 찾는 함수
def fit_rectangular_prism_to_points(points,
                                    box_dimensions,
                                    initial_guess,
                                    soft_constraints=None,
                                    b_callback=True
                                    ) ->dict:
    """
    Fit a rectangular prism to a set of points by optimizing translation and rotation.

    Parameters:
        points (numpy.ndarray): Nx3 array of points (x, y, z).
        box_dimensions (list): Dimensions of the rectangular prism [width, length, height].
        initial_guess (list): Initial guess for translation and rotation [tx, ty, tz, rz, ry, rx].
        soft_constraints (list): List of soft constraints in the form [(index, edge_number, distance), ...].

    Returns:
        dict: Optimized translation and rotation parameters.
    """
    # Remove rows with NaN values
    points = points[~np.isnan(points).any(axis=1)]
    if points.shape[0] < 1:
        print("Error: No valid points available after removing NaN values.")
        return None, None, None

    if points.shape[0] < 3:
        print(f"Warning: OBB fitting is recommended for at least 3 points. Current points: {points.shape[0]}")
        return None, None, None

    # Extract box dimensions
    w, l, h = box_dimensions
    box_half_extents = np.array([w / 2, l / 2, h / 2])

    # Define the rectangular prism vertices in local coordinates
    box_vertices = np.array([
        [-w / 2, -l / 2, -h / 2],
        [ w / 2, -l / 2, -h / 2],
        [ w / 2,  l / 2, -h / 2],
        [-w / 2,  l / 2, -h / 2],
        [-w / 2, -l / 2,  h / 2],
        [ w / 2, -l / 2,  h / 2],
        [ w / 2,  l / 2,  h / 2],
        [-w / 2,  l / 2,  h / 2],
    ])

    # Define the objective function
    def objective(params):
        tx, ty, tz, rz, ry, rx = params

        # Compute the rotation matrix (ZYX order)
        euler_angles = np.array([rz, ry, rx])
        translation = np.array([tx, ty, tz])
        rotation = Rotation.from_euler('zyx', euler_angles, degrees=False)
        rotation_matrix = rotation.as_matrix()

        # Transform the box vertices
        transformed_vertices = (rotation_matrix @ box_vertices.T).T + translation

        # Define the planes of the rotated box
        planes = [
            (rotation_matrix @ np.array([-1, 0, 0]), transformed_vertices[0]),  # Left face
            (rotation_matrix @ np.array([1, 0, 0]), transformed_vertices[1]),   # Right face
            (rotation_matrix @ np.array([0, -1, 0]), transformed_vertices[0]),  # Front face
            (rotation_matrix @ np.array([0, 1, 0]), transformed_vertices[2]),   # Back face
            (rotation_matrix @ np.array([0, 0, -1]), transformed_vertices[0]),  # Bottom face
            (rotation_matrix @ np.array([0, 0, 1]), transformed_vertices[4]),   # Top face
        ]

        # Compute the distance from each point to the closest face of the box
        total_distance = 0
        for point in points:
            # Compute the perpendicular distance to each plane
            plane_distances = [
                abs(np.dot(plane[0], point - plane[1])) / np.linalg.norm(plane[0])
                for plane in planes
            ]
            # Add the minimum distance to the total
            total_distance += min(plane_distances)

        # Add penalty for soft constraints
        if soft_constraints:
            for index, edge_number, target_distance in soft_constraints:
                point = points[index]
                edge_vertex = transformed_vertices[edge_number]
                edge_distance = np.linalg.norm(point - edge_vertex)
                total_distance += (edge_distance - target_distance) ** 2  # Penalty term

        return total_distance

    # Define a callback function to track progress
    def callback(params):
        current_error = objective(params)
        #print(f"Iteration {iteration['count']}: total_error = {current_error:.6f}, params = {params}")
        print(f"Iteration {iteration['count']}: total_error = {current_error:.6f}")
        iteration["count"] += 1

    # Optimize the parameters
    iteration = {"count": 0}
    callback_func = None
    if b_callback:
        callback_func = callback
    result = minimize(objective, initial_guess, method='L-BFGS-B', callback=callback_func)
    # Extract the optimized parameters
    optimized_params = result.x
    tra = np.array(optimized_params[:3])
    rot = Rotation.from_euler('zyx', optimized_params[3:], degrees=False)
    rot_matrix = rot.as_matrix()
    # Compute the final box vertices
    canonical_vertices = get_canonical_box_vertices(box_half_extents)
    final_vertices = (rot_matrix @ canonical_vertices.T).T + tra

    return {
        "translation": optimized_params[:3],
        "rotation": optimized_params[3:],
        "rotation_matrix": rot_matrix,
        "success": result.success,
        "message": result.message,
        'box_vertices': final_vertices,
    }

# PyVista로 VTK 파일 시각화 함수 (라벨 포함)
def visualize_vtk_file_with_labels(vtk_file, points, w, l, h):
    """
    Visualize a VTK file using PyVista with labels for edges, faces, and vertices.

    Parameters:
        vtk_file (str): Path to the VTK file.
        points (numpy.ndarray): Points of the rectangular prism.
        w, l, h (float): Dimensions of the rectangular prism.
    """
    # Load the VTK file
    mesh = pv.read(vtk_file)

    # Create a PyVista plotter
    #plotter = pv.Plotter()
    plotter = BackgroundPlotter()

    # Add the mesh
    plotter.add_mesh(mesh, color="lightblue", show_edges=True)

    '''
    # Add labels for vertices
    for i, point in enumerate(points):
        plotter.add_point_labels([point], [f"V{i+1}"], point_size=10, font_size=10, text_color="black")

    # Add labels for edges
    edge_labels = [
        ("E1", [-w / 2, 0, 0]),
        ("E2", [w / 2, 0, 0]),
        ("E3", [0, -l / 2, 0]),
        ("E4", [0, l / 2, 0]),
        ("E5", [0, 0, -h / 2]),
        ("E6", [0, 0, h / 2]),
    ]
    for label, position in edge_labels:
        plotter.add_point_labels([position], [label], point_size=10, font_size=10, text_color="blue")

    # Add labels for faces
    face_labels = [
        ("F1", [0, 0, -h / 2]),
        ("F2", [0, 0, h / 2]),
        ("F3", [0, -l / 2, 0]),
        ("F4", [0, l / 2, 0]),
        ("F5", [-w / 2, 0, 0]),
        ("F6", [w / 2, 0, 0]),
    ]
    for label, position in face_labels:
        plotter.add_point_labels([position], [label], point_size=10, font_size=10, text_color="green")
    '''
    # Show the plot
    plotter.show()

# 입력 문자열에서 점 데이터 파싱 함수 (하드코딩된 문자열 처리를 위해 내부적으로 사용)
def parse_point_string_internal(point_string):
    """ 공백/탭으로 구분된 숫자 문자열을 N x 3 형태의 3D 점 numpy 배열로 파싱합니다. """
    try:
        numbers = [float(x) for x in point_string.split()]
        if len(numbers) % 3 != 0: print(f"Error: 입력된 숫자의 총 개수({len(numbers)})가 3의 배수가 아닙니다 (x, y, z 쌍이 맞지 않음)."); return None
        points = np.array(numbers).reshape(-1, 3)
        #print(f"Successfully parsed {points.shape[0]} points from the input string.")
        return points
    except ValueError: print("Error: 입력 문자열에 숫자로 변환할 수 없는 값이 포함되어 있습니다."); return None
    except Exception as e: print(f"An unexpected error occurred during parsing: {e}"); return None

def parse_point_array_internal(point_array):
    """
    주어진 numpy 배열을 N x 3 형태의 3D 점 numpy 배열로 변환합니다.

    Parameters:
        point_array (np.ndarray): 1D 또는 2D numpy 배열. 1D 배열은 길이가 3의 배수여야 하며, 2D 배열은 Nx3 형태여야 합니다.

    Returns:
        np.ndarray: N x 3 형태의 3D 점 배열. 유효하지 않은 입력 시 None 반환.
    """
    try:
        # 입력이 1D 배열인 경우
        if point_array.ndim == 1:
            if len(point_array) % 3 != 0:
                print(f"Error: 입력된 배열의 길이({len(point_array)})가 3의 배수가 아닙니다 (x, y, z 쌍이 맞지 않음).")
                return None
            points = point_array.reshape(-1, 3)
        # 입력이 2D 배열인 경우
        elif point_array.ndim == 2 and point_array.shape[1] == 3:
            points = point_array
        else:
            print("Error: 입력 배열은 1D (길이 3의 배수) 또는 2D (Nx3) 형태여야 합니다.")
            return None

        #print(f"Successfully parsed {points.shape[0]} points from the input array.")
        return np.array(points, dtype=np.float64)
    except Exception as e:
        #print(f"An unexpected error occurred during parsing: {e}")
        return None
    #end def

def save_vtk_collection(frame_files, output_pvd, time_arr):
    """
    여러 VTK 파일을 하나의 PVD 파일로 묶어 애니메이션 가능하게 저장합니다.

    Parameters:
        frame_files (list): 생성된 VTK 파일들의 경로 리스트.
        output_pvd (str): 출력할 PVD 파일 경로.
        time_arr (np.array): 각 프레임의 시간 값 (time_arr[i]는 frame_files[i]의 시간).
    """
    pvd_content = '''<?xml version="1.0"?>
<VTKFile type="Collection" version="0.1" byte_order="LittleEndian">
  <Collection>
    {}
  </Collection>
</VTKFile>'''.format('\n'.join([
        f'<DataSet timestep="{t:.6f}" group="" part="0" file="{f}"/>'
        for t, f in zip(time_arr, frame_files)
    ]))
    with open(output_pvd, 'w') as f:
        f.write(pvd_content)
    print(f"생성된 PVD 파일: {output_pvd}")
    #end def
def PlotMotionData(times,
                   df:pd.DataFrame=None,
                   point_list:list=None,
                   title:str=None,
                   b_block=False,
                   ):
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm

    #time_arr = df.iloc[:, 0].values  # 첫 번째 열을 시간으로 사용

    # 컬럼 수에 따라 색상 설정
    colors = mpl.colormaps['tab10']
    # 서브플롯 생성 (1행 3열)
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))  # 가로로 3개의 서브플롯 생성
    if title is not None:
        plt.suptitle(title, fontsize=12, y=1.02, ha='center')

    # 첫 번째 서브플롯: x 리스트
    axes[0].set_title('X')
    axes[0].set_xlabel('Time(s)')
    axes[0].set_ylabel('Value')
    # 두 번째 서브플롯: y 리스트
    axes[1].set_title('Y')
    axes[1].set_xlabel('Time(s)')
    axes[1].set_ylabel('Value')
    # 세 번째 서브플롯: z 리스트
    axes[2].set_title('Z')
    axes[2].set_xlabel('Time(s)')
    axes[2].set_ylabel('Value')
    #
    if df is not None:
        #num_columns = len(df.columns)
        for i in range(0, len(df.columns), 3):
            columns_group = df.columns[i:i+3]
            data_group = df[columns_group]
            #print(data_group)
            axes[0].plot( times, data_group.iloc[:,0], label=columns_group[0], color=colors(np.random.rand()) )
            axes[1].plot( times, data_group.iloc[:,1], label=columns_group[1], color=colors(np.random.rand()) )
            axes[2].plot( times, data_group.iloc[:,2], label=columns_group[2], color=colors(np.random.rand()) )
            #end for
    #
    if point_list is not None:
        xs = [v[0] for v in point_list]
        ys = [v[1] for v in point_list]
        zs = [v[2] for v in point_list]
        axes[0].plot( times, xs, label='x', color=colors(np.random.rand()) )
        axes[1].plot( times, ys, label='y', color=colors(np.random.rand()) )
        axes[2].plot( times, zs, label='z', color=colors(np.random.rand()) )
    #
    for ax in axes:
    #    ax.legend()
        pass
    #
    # 레이아웃 조정 및 표시
    plt.tight_layout()
    plt.show(block=b_block)

# Example usage
def Usage1():
    # 하드코딩된 3차원 점들 데이터 (텍스트 문자열)
    #user_point_string_hardcoded = "260.831055 1127.373901 301.493713 -655.467407 773.359314 405.582428 270.191284 774.795349 290.854584 1204.676147 1128.348389 194.559555 1336.570923 224.183075 315.691406 1328.514282 702.934082 303.530029 1320.46521 1118.294067 296.003204 1209.546631 222.249084 220.791367 1204.6427 724.705444 199.435211 262.179565 211.812729 305.443726 -737.018005 203.350128 487.759644 -739.916565 638.502502 505.781281 -638.361816 1102.13208 608.016663 292.424866 695.380981 522.347168 1222.003662 1117.536499 399.420044 291.367798 1126.685303 506.632202 1214.415771 685.023804 411.527405 -630.51178 609.290527 607.766907 -625.685913 166.036331 594.814087 304.597015 215.74617 518.827576 1218.660034 199.235886 426.676392 -636.914246 215.725601 392.976288 -666.402222 1116.217529 410.927185 -741.662964 1115.706421 531.172058"
    user_point_string_hardcoded = "-329.671387	1121.304321	228.644592	-1254.354614	774.614502	205.592026	-321.731049	768.655151	219.26886	619.889587	1114.745483	252.542313	726.701599	209.656509	390.342926	724.188477	688.447144	377.358887	720.542664	1103.852051	368.943817	613.925415	208.655716	278.87326	615.987244	711.119202	257.223785	-336.134216	205.764297	232.417755	-1350.946899	205.328049	275.569672	-1352.8479	640.50293	293.175781	-1262.649048	1103.391235	408.571777	-332.177643	689.238586	451.591309	608.790344	1103.948608	457.835327	-327.645416	1120.526123	436.033295	596.18219	671.518188	468.630524	-1258.744995	610.503113	409.229248	-1255.695801	167.215195	396.905945	-323.438232	209.520157	449.609192	594.452881	185.723282	484.046997	-1238.66333	216.842529	195.459625	-1263.203369	1117.552246	209.503647	-1354.288696	1117.724365	318.254364	-760.693176	356.673767	435.536987	-747.216431	869.726868	434.792084	185.567474	432.539825	244.233017	178.430679	699.993347	234.996994	194.641434	968.840149	235.091873	616.309021	1208.638672	370.715332	-322.153168	1213.146729	339.771912	-1263.226685	1212.04895	320.594299"
    point_on_face_pairs = [(30-1, 3-1, 1.0), (32-1, 3-1, 1.0), ]    # point가 위치한 face를 알고 있는 경우, 제약 조건으로 지정
    # 하드코딩된 문자열에서 점 데이터 파싱 (내부 함수 사용)
    points_for_fitting = parse_point_string_internal(user_point_string_hardcoded)

    # 맞춰야 할 직육면체의 크기 (L, W, H 순서라고 가정) 기본값 변경
    fixed_box_dimensions = [2070.0, 1200.0, 200.0]  # 기본값 사용
    box_size_lwh = fixed_box_dimensions
    elem_nums = [int(b / 50.0) for b in box_size_lwh]  # 50mm 간격으로 나누기

    # --- 고정 크기 OBB 피팅 실행 ---
    print("\n--- 고정 크기 OBB 피팅 결과 ---")
    # max_iterations 및 tolerance 값을 변경하여 호출
    fitted_box_vertices, fitted_rotation_matrix, fitted_center = fit_oriented_box_to_surface(
        points_for_fitting, fixed_box_dimensions, max_iterations=1500, tolerance=1e-12,
        point_on_face_pairs=point_on_face_pairs,
    )
    # zyx 순서로 회전 행렬을 오일러 각도로 변환
    euler_angles_rad = rotation_matrix_to_euler_angles(fitted_rotation_matrix, convention='zyx', degrees=False)
    output_file = "optimized_rectangular_mesh.vtk"
    create_rectangular_mesh(
        box_size_lwh=box_size_lwh,
        elem_nums=elem_nums,
        translation=fitted_center,
        rotation=euler_angles_rad,
        output_file=output_file
    )
    # Visualize the optimized rectangular mesh
    visualize_vtk_file(output_file, points=points_for_fitting, box_vertices=fitted_box_vertices)

    ############################
    print ( fitted_center, euler_angles_rad)
    # Fit the rectangular prism
    initial_guess = np.concatenate( (fitted_center, euler_angles_rad) )
    soft_constraints = []  # Soft constraints (optional)
    result = fit_rectangular_prism_to_points(points_for_fitting, fixed_box_dimensions, initial_guess, soft_constraints)
    #
    # Print the optimization result
    print("Initial Translation:", fitted_center)
    print("Initial Rotation (ZYX):", euler_angles_rad)
    print("Optimized Translation:", result["translation"])
    print("Optimized Rotation (ZYX):", result["rotation"])
    print("Optimization Success:", result["success"])
    print("Message:", result["message"])
    #
    # Use the optimized parameters to recreate the rectangular mesh
    optimized_translation = tuple(result["translation"])
    optimized_rotation = tuple(result["rotation"])  # Convert radians to degrees
    #
    # Recreate the rectangular mesh with the optimized parameters
    output_file = "optimized_rectangular_mesh.vtk"
    create_rectangular_mesh(
        box_size_lwh=box_size_lwh,
        elem_nums=elem_nums,
        translation=optimized_translation,
        rotation=optimized_rotation,
        output_file=output_file
    )
    # Visualize the optimized rectangular mesh
    visualize_vtk_file(output_file, points=points_for_fitting,
                        box_vertices=result['box_vertices'])



def Usage2():
    '''
    csv 파일에서 시간별로 points 데이터의 위치를 읽어오고, 직육면체 회전, 병진 정보를 순차적으로 얻는다.
    '''
    # 맞춰야 할 직육면체의 크기 (L, W, H 순서라고 가정) 기본값 변경
    #fixed_box_dimensions = [2070.0, 1200.0, 200.0]  # 기본값 사용
    #point_on_face_pairs = [(30-1, 4-1, 1.0), (31-1, 4-1, 1.0), (32-1, 4-1, 1.0), ]    # point가 위치한 face를 알고 있는 경우, 제약 조건으로 지정
    #fixed_box_dimensions = [1578/2, 930/2, 142/2]  # 기본값 사용
    fixed_box_dimensions = [1578., 930., 142.]  # 기본값 사용
    point_on_face_pairs = [(3-1, 3-1, 5.0), (6-1, 3-1, 5.0), (27-1, 3-1, 5.0), ]    # point가 위치한 face를 알고 있는 경우, 제약 조건으로 지정
    box_size_lwh = fixed_box_dimensions
    elem_nums = [int(b / 50.0) for b in box_size_lwh]  # 50mm 간격으로 나누기

    #
    #
    #file_path = r'D:\STUDY\ABQ_PYTHON_WORKS\DropMotionAnalysis\motion_data\0417_VD_TEST\VDtest_S2_005.csv'
    #file_path = r'D:\PRJ_2025\VD\TI_MOTION\TestData_motionTech\Case7. 24카메라-비대칭-전면 코너1.csv'
    #file_path = r'D:\PRJ_2025\VD\TI_MOTION\TestData_D0430_ChaMinWoo\0424 65inch front drop(Final).csv'
    file_path = r'D:\PRJ_2025\VD\TI_MOTION\TestData_D0508\0508_65_Box_RobotArm_ISTA - 1STEP.csv'
    output_base_path = r'D:\PRJ_2025\VD\TI_MOTION\TestData_D0508'
    file_name_ext = os.path.basename(file_path)
    file_name = os.path.splitext(file_name_ext)[0]
    mcd = MotionCaptureData()
    mcd.load_csv(file_path)

    # 데이터 확인용 Plot
    PlotMotionData(mcd.time_arr, mcd.df_rigidbody_marker)
    data_set_xml = ''
    ### BOX FITTING AND SHOWVTK
    #frame = 100
    frame_list = range(0, len(mcd.time_arr), 2)  # 실 데이터 출력 시에 사용
    #frame_list = [1000, ]
    ref_center = None
    ref_rotation_matrix = None
    for frame in frame_list:
        df = mcd.df_rigidbody_marker    # riht_body marker, marker, or both of them
        n_rows = df.shape[0]
        #col_series = df.iloc[0, n_col_w*7+2:n_col_w*7+2 + 32*3]
        col_series = df.iloc[frame, :]
        parsed_points = parse_point_array_internal(col_series.values)
        fitted_box_vertices, fitted_rotation_matrix, fitted_center_translation = fit_oriented_box_to_surface(
            parsed_points, fixed_box_dimensions, max_iterations=1500, tolerance=1e-12,
            point_on_face_pairs=point_on_face_pairs,
            ref_center=ref_center,
            ref_rotation_matrix=ref_rotation_matrix,
            )
        euler_angles_rad = rotation_matrix_to_euler_angles(fitted_rotation_matrix, convention='ZYX', degrees=False)
        euler_angles_deg = rotation_matrix_to_euler_angles(fitted_rotation_matrix, convention='ZYX', degrees=True)
        print( "Rotation Matrix:", fitted_rotation_matrix)
        print( "Initial Translation:", fitted_center_translation)
        print( "Initial Rotation, ZYX, rad:", euler_angles_rad)
        print( "Initial Rotation, ZYX, deg:", euler_angles_deg)
        ref_center = fitted_center_translation
        ref_rotation_matrix = fitted_rotation_matrix
        output_file = os.path.join(output_base_path, f"{file_name}_{frame:04d}.vtk")
        print(f"Output file: {output_file}")
        create_rectangular_mesh(
            box_size_lwh=box_size_lwh,
            elem_nums=elem_nums,
            translation=fitted_center_translation,
            rotation=euler_angles_rad,
            rotation_matrix=fitted_rotation_matrix,
            output_file=output_file
        )
        data_set_xml += f'<DataSet timestep="{frame}" file="{output_file}" />\n'

    pvd_content = pvd_base.replace("<DataSet/>", data_set_xml)
    with open(f"{file_name}.pvd", "w") as f:
        f.write(pvd_content)

    # Visualize the optimized rectangular mesh
    visualize_vtk_file(vtk_file=output_file, points=parsed_points, box_vertices=fitted_box_vertices)

    return df

def Usage3(csv_file_path = None):
    '''
    rigid body data plot 확인용
    '''
    #
    #file_path = r'D:\PRJ_2025\VD\TI_MOTION\TestData_D0508\0508_65_Box_RobotArm_ISTA - 1STEP.csv'
    file_path = csv_file_path
    file_name_ext = os.path.basename(file_path)
    file_name = os.path.splitext(file_name_ext)[0]
    mcd = MotionCaptureData()
    mcd.load_csv(file_path)
    # 데이터 확인용 Plot
    PlotMotionData(mcd.time_arr, mcd.df_rigidbody_marker, b_block=True)
    #end def

def Usage4(
        csv_file_path = r"",
        vtk_save_file_path = None,  # base_path와 확장자를 제외한 파일명
        fixed_box_dimensions=[1578., 930., 142.],
        point_on_face_pairs = [], # [(3-1, 3-1, 5.0), (6-1, 3-1, 5.0), (27-1, 3-1, 5.0), ],    # point가 위치한 face를 알고 있는 경우, 제약 조건으로 지정
        time_min=218., time_max=220.,
        opt_edge_constraints = [],
        b_optimization = True,
        b_check_pv_plot = True,
        ):
    '''
    주어진 time_min, time_max에 대한 motion 추적 및 박스 형성
    '''
    #file_path = r'D:\PRJ_2025\VD\TI_MOTION\TestData_D0508\0508_65_Box_RobotArm_ISTA - 1STEP.csv'
    file_path:str = csv_file_path
    file_name_ext = os.path.basename(file_path)
    file_name = os.path.splitext(file_name_ext)[0]
    mcd = MotionCaptureData()
    mcd.load_csv(file_path)

    # 원하는 time 영역의 index 확인
    mask = (mcd.time_arr >= time_min) & (mcd.time_arr <= time_max)
    frame_list = np.where(mask)[0]
    time_list = mcd.time_arr[mask]
    #print (time_indices)

    # 해당 index plot
    PlotMotionData(time_list, mcd.df_rigidbody_marker.iloc[frame_list], b_block=True)

    data_set_xml = ''
    #fixed_box_dimensions = [1578., 930., 142.]  # 기본값 사용
    #point_on_face_pairs = [(3-1, 3-1, 5.0), (6-1, 3-1, 5.0), (27-1, 3-1, 5.0), ]    # point가 위치한 face를 알고 있는 경우, 제약 조건으로 지정
    box_size_lwh = fixed_box_dimensions
    elem_nums = [int(b / 50.0) for b in box_size_lwh]  # 50mm 간격으로 나누기

    ### BOX FITTING AND SHOWVTK
    #frame = 100
    #frame_list = range(0, len(mcd.time_arr), 2)  # 실 데이터 출력 시에 사용
    ref_center = None
    ref_rotation_matrix = None
    rotation_euler_rad_results = []
    rotation_euler_deg_results = []
    rotation_matrix_results = []
    translation_results = []
    frame_files = []

    # 최초 dummy 진행
    df = mcd.df_rigidbody_marker    # riht_body marker, marker, or both of them
    col_series = df.iloc[frame_list[0], :]
    parsed_points = parse_point_array_internal(col_series.values)
    fitted_box_vertices, fitted_rotation_matrix, fitted_center_translation = fit_oriented_box_to_surface(
            parsed_points, fixed_box_dimensions, max_iterations=2500, tolerance=1e-12,
            point_on_face_pairs=point_on_face_pairs,
            ref_center=ref_center,
            ref_rotation_matrix=ref_rotation_matrix,
            )
    ref_center = fitted_center_translation
    ref_rotation_matrix = fitted_rotation_matrix
    print( "Rotation Matrix:", fitted_rotation_matrix)
    print( "Initial Translation:", fitted_center_translation)
    #
    for frame_idx, frame in enumerate(frame_list):
        df = mcd.df_rigidbody_marker    # riht_body marker, marker, or both of them
        n_rows = df.shape[0]
        #col_series = df.iloc[0, n_col_w*7+2:n_col_w*7+2 + 32*3]
        col_series = df.iloc[frame, :]
        parsed_points = parse_point_array_internal(col_series.values)
        fitted_box_vertices, fitted_rotation_matrix, fitted_center_translation = fit_oriented_box_to_surface(
            parsed_points, fixed_box_dimensions, max_iterations=2500, tolerance=1e-12,
            point_on_face_pairs=point_on_face_pairs,
            ref_center=ref_center,
            ref_rotation_matrix=ref_rotation_matrix,
            )
        euler_angles_rad = rotation_matrix_to_euler_angles(fitted_rotation_matrix, convention='zyx', degrees=False)
        euler_angles_deg = rotation_matrix_to_euler_angles(fitted_rotation_matrix, convention='zyx', degrees=True)
        print( "Rotation Matrix:", fitted_rotation_matrix)
        print( "Initial Translation:", fitted_center_translation)
        print( "Initial Rotation, ZYX, rad:", euler_angles_rad)
        print( "Initial Rotation, ZYX, deg:", euler_angles_deg)

        if b_optimization:
            initial_guess = np.concatenate( np.array( (fitted_center_translation, euler_angles_rad) ) )
            #opt_edge_constraints = []  # Soft constraints (optional)
            result = fit_rectangular_prism_to_points(parsed_points, fixed_box_dimensions, initial_guess, opt_edge_constraints, b_callback=False)
            #
            fitted_rotation_matrix = result["rotation_matrix"]
            fitted_center_translation = result["translation"]
            euler_angles_rad = rotation_matrix_to_euler_angles(fitted_rotation_matrix, convention='zyx', degrees=False)
            euler_angles_deg = rotation_matrix_to_euler_angles(fitted_rotation_matrix, convention='zyx', degrees=True)
            # Print the optimization result
            print("Optimized Translation:", fitted_center_translation)
            print("Optimized Rotation, ZYX, rad:", euler_angles_rad)
            print("Optimized Rotation, ZYX, deg:", euler_angles_deg)
            print("Optimization Success:", result["success"])
            print("Message:", result["message"])
            #

        #
        translation_results.append(fitted_center_translation)
        rotation_euler_rad_results.append(euler_angles_rad)
        rotation_euler_deg_results.append(euler_angles_deg)
        rotation_matrix_results.append(fitted_rotation_matrix)
        #
        ref_center = fitted_center_translation
        ref_rotation_matrix = fitted_rotation_matrix
        #output_file = os.path.join(output_base_path, f"{file_name}_{frame:04d}.vtk")
        output_file = f"{vtk_save_file_path}_{frame:04d}.vtp"
        print(f"Output file: {output_file}")
        if frame_idx > 0 :
            create_rectangular_mesh(
                box_size_lwh=box_size_lwh,
                elem_nums=elem_nums,
                translation=fitted_center_translation,
                rotation=euler_angles_rad,
                rotation_matrix=fitted_rotation_matrix,
                output_file=output_file
            )
        # 첫 프레임은 우선 show 하여 체크
        if frame_idx == 1 and b_check_pv_plot :
            visualize_vtk_file(vtk_file=output_file, points=parsed_points, box_vertices=fitted_box_vertices)
        frame_files.append(output_file)
        #end for

    # Visualize the optimized rectangular mesh
    if b_check_pv_plot :
        visualize_vtk_file(vtk_file=output_file, points=parsed_points, box_vertices=fitted_box_vertices)

    # translation plot
    PlotMotionData(times=time_list[1:], point_list=translation_results[1:])
    # rotation plot
    PlotMotionData(times=time_list[1:], point_list=rotation_euler_deg_results[1:])

    # pvd saved
    save_vtk_collection(frame_files=frame_files[1:], output_pvd=f'{vtk_save_file_path}.pvd', time_arr=frame_list[1:])

    mcd.output_translation_results = translation_results[1:]
    mcd.output_rotation_euler_rad_results = rotation_euler_rad_results[1:]
    mcd.output_rotation_euler_deg_results = rotation_euler_deg_results[1:]
    mcd.output_rotation_matrix_results = rotation_matrix_results[1:]
    mcd.output_frame_list = frame_list[1:]
    mcd.output_time_list = time_list[1:]
    mcd.output_df_rigidbody_marker = mcd.df_rigidbody_marker.iloc[frame_list[1:], :].copy()

    return mcd
    #end def

translation_results = None
rotation_results = None

def MainTest1():
    box_dimensions = [1578., 930., 142.]
    frame_list = []
    translation_results = []
    rotation_matrix_results = []
    #Usage1()
    #Usage2()
    # Usage3 : CSV Data 체크 - RigidBodyData
    Usage3(csv_file_path = r'D:\PRJ_2025\VD\TI_MOTION\TestData_D0508\0508_65_Box_RobotArm_ISTA - 1STEP.csv')
    #"""
    #translation_results, rotation_euler_rad_results, rotation_euler_deg_results, rotation_matrix_results, frame_list = Usage4(
    mcd = Usage4(
        csv_file_path = r'D:\PRJ_2025\VD\TI_MOTION\TestData_D0508\0508_65_Box_RobotArm_ISTA - 1STEP.csv',
        vtk_save_file_path = r'D:\PRJ_2025\VD\TI_MOTION\TestData_D0508\A_175_220',
        fixed_box_dimensions=box_dimensions,
        point_on_face_pairs =[
            (9-1, 3-1, 5.0), (14-1, 3-1, 5.0), (18-1, 3-1, 5.0),
            (22-1, 2-1, 5.0), (21-1, 2-1, 5.0), (19-1, 2-1, 5.0), (20-1, 2-1, 5.0),
            (6-1, 5-1, 5.0), (1-1, 5-1, 5.0),
            ],
        time_min=151.0, time_max=153.3,     # 꼭지점 낙하
        #time_min=61.2, time_max=62.3,        # 모서리 낙하
        opt_edge_constraints =  [
            #(17-1, 1-1, 100.0),
            #(17-1, 7-1, 100.0),
            #(10-1, 1-1, 100.0),
            #(10-1, 5-1, 100.0),

            #(24-1, 8-1, 100.0),
            #(24-1, 2-1, 100.0),
            #(25-1, 6-1, 100.0),
            #(25-1, 2-1, 100.0),
            ],
        b_optimization = False,
        b_check_pv_plot = True,    # True:  marker point들의 위치와 box 상의 위치를 체크하기 위한 목적
        )
    #"""
    ### MCD 정보(box 중심의 회전, 병진 정보)를 이용해 box의 모서리 점의 위치, 변위, 속도의 계산
    pmf = PointMotionFields(mcd=mcd)
    box_vertices = pmf.get_points_by_box( box_dimensions = box_dimensions,  center = [0, 0, 0] )
    pmf.calc(points=box_vertices)    # position, displacement, velocity
    #
    PlotMotionData(times=mcd.output_time_list, df=pmf.output_df_velocity, b_block=False)
    PlotMotionData(times=mcd.output_time_list, df=pmf.output_df_displacement, b_block=False)
    PlotMotionData(times=mcd.output_time_list, df=pmf.output_df_position, b_block=False)
    # 3D Viewer
    rigid_box_animation(box_dimensions, mcd, pmf)

    # df, x,y,z, x,y,z ,...

    input("Press Enter to exit...")

    # point_on_face_pairs는 gap이 없는 marker에 대해서 설정하는 것이 유리하다! 그렇지 않으면 엉뚱한 fit
    #end if

def MainTest2():
    """
    D:\\PRJ_2025\\VD\\TI_MOTION\\TestData_D0509
    75 inch
    D:\\PRJ_2025\\VD\\TI_MOTION\\TestData_D0509\\0509_75Box ISTA FULL.csv
    ○ 모델 : 75U8000F
    ○ BOX 사이즈 (W x H x D) : 1820mm x 1100mm x 164mm
    ○ BOX 포장 후 무게 : 31.0 kg
    ○ 마커 수량 : 26EA (Front/Back/Top/Left/Right – 9ea/8ea/3ea/3ea/3ea)
    53.8 - 54.8

    """
    box_dimensions = [1820., 1100., 164.]       # 75 inch
    frame_list = []
    translation_results = []
    rotation_matrix_results = []
    #Usage1()
    #Usage2()
    csv_file_path = r'D:\PRJ_2025\VD\TI_MOTION\TestData_D0509\0509_75Box ISTA FULL.csv'
    ### csv 파일 확인, Y 좌표 변화를 토대로 낙하 횟수 판단
    Usage3(csv_file_path = csv_file_path)
    #"""
    ### point_on_face_pair 설정 없이 fit 수행 시, 모델의 face와 시험의 marker 위치를 확인함.
    #   이 과정에서는 animation 등은 진행하지 않아도 됨.
    #
    #translation_results, rotation_euler_rad_results, rotation_euler_deg_results, rotation_matrix_results, frame_list = Usage4(
    mcd = Usage4(
        csv_file_path = csv_file_path,
        vtk_save_file_path = r'D:\PRJ_2025\VD\TI_MOTION\TestData_D0509\vtk_1\A_0',
        fixed_box_dimensions=box_dimensions,
        point_on_face_pairs =[
            (12-1, 3-1, 5.0), (15-1, 3-1, 5.0), (26-1, 3-1, 5.0),
        #    (9-1, 3-1, 5.0), (14-1, 3-1, 5.0), (18-1, 3-1, 5.0),
        #    (22-1, 2-1, 5.0), (21-1, 2-1, 5.0), (19-1, 2-1, 5.0), (20-1, 2-1, 5.0),
        #    (6-1, 5-1, 5.0), (1-1, 5-1, 5.0),
         ],
        #time_min=151.0, time_max=153.3,     # 모서리 낙하
        time_min=53.9, time_max=54.5,        # scean1
        #time_min=53.8, time_max=54.8,        # ?
        opt_edge_constraints =  [
            #(17-1, 1-1, 100.0),
            #(17-1, 7-1, 100.0),
            #(10-1, 1-1, 100.0),
            #(10-1, 5-1, 100.0),

            #(24-1, 8-1, 100.0),
            #(24-1, 2-1, 100.0),
            #(25-1, 6-1, 100.0),
            #(25-1, 2-1, 100.0),
            ],
        b_optimization = False,
        b_check_pv_plot = True,     # True:  marker point들의 위치와 box 상의 위치를 체크하기 위한 목적
        )
    #"""
    ### MCD 정보(box 중심의 회전, 병진 정보)를 이용해 box의 모서리 점의 위치, 변위, 속도의 계산
    pmf = PointMotionFields(mcd=mcd)
    box_vertices = pmf.get_points_by_box( box_dimensions = box_dimensions,  center = [0, 0, 0] )
    pmf.calc(points=box_vertices)    # position, displacement, velocity
    #
    PlotMotionData(times=mcd.output_time_list, df=pmf.output_df_velocity, title="Vertice Velocity", b_block=False)
    PlotMotionData(times=mcd.output_time_list, df=pmf.output_df_displacement, title="Vertice Displacement", b_block=False)
    PlotMotionData(times=mcd.output_time_list, df=pmf.output_df_position, title="Vertice Position", b_block=False)
    # 3D Viewer
    rigid_box_animation(box_dimensions, mcd, pmf)

    # df, x,y,z, x,y,z ,...

    input("Press Enter to exit...")

    # point_on_face_pairs는 gap이 없는 marker에 대해서 설정하는 것이 유리하다! 그렇지 않으면 엉뚱한 fit
    #end if

if __name__ == "__main__":
    # 0508_65_Box_RobotArm_ISTA - 1STEP.csv
    #MainTest1()

    #D25-05-15, 0509_75Box ISTA FULL
    MainTest2()

    #end if
