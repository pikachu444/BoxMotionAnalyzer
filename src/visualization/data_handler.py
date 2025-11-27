import pandas as pd
import numpy as np
import re
from src.visualization import config
from src.config.data_columns import TimeCols, RigidBodyCols

class DataHandler:
    def __init__(self):
        self.visualization_dataframe = None
        self.n_frames = 0
        self.object_ids = []

    def load_analysis_result(self, filepath: str) -> bool:
        """
        Loads the BoxMotionAnalyzer result CSV (Single Header) and transforms it
        into the long-format DataFrame expected by the visualizer.
        """
        try:
            # 1. Load CSV
            df = pd.read_csv(filepath)
            
            # 2. Check for required Time/Frame columns
            # We prefer Frame, but if not present, we can generate it or use Time.
            # config.DF_FRAME is mapped to TimeCols.FRAME ("Frame")
            if TimeCols.FRAME not in df.columns:
                if TimeCols.TIME in df.columns:
                    # Generate Frame from Time (assuming constant FPS or just sequential)
                    # Or just use index as frame
                    df[TimeCols.FRAME] = range(len(df))
                else:
                    print(f"[ERROR] Neither '{TimeCols.FRAME}' nor '{TimeCols.TIME}' column found.")
                    return False

            # 3. Identify Object Columns (X, Y, Z triplets)
            # We look for columns ending in _X, _Y, _Z
            # Regex to capture Object ID and Axis
            # Pattern: (ObjectID)_(X|Y|Z)
            # We exclude columns that are clearly not positions (like velocities if they follow different naming)
            # But header_converter.py produces C1_V_X etc.
            # We want Position.
            # RigidBody: RigidBody_Position_X -> ID: RigidBody_Position
            # Corner: C1_X -> ID: C1
            # Marker: MK_BTM_1_X -> ID: MK_BTM_1
            
            # We filter columns that match the pattern
            position_cols = []
            object_ids = set()
            
            # Map: { 'C1': {'X': 'C1_X', 'Y': 'C1_Y', ...}, ... }
            objects_map = {}

            for col in df.columns:
                # Check for X, Y, Z suffixes
                # Using a regex that allows any characters for ID, but ends with _X, _Y, _Z
                # We need to be careful about Velocity (_Vx, _Vy) or other analysis columns.
                # data_columns.py defines suffixes.
                # CornerCoordCols.X_SUFFIX is "_X"
                
                # Simple heuristic: Ends with _X, _Y, _Z (case sensitive usually, but let's check data_columns)
                # RigidBodyCols.POS_X is "RigidBody_Position_X"
                
                match = re.match(r"^(?P<id>.+)_(?P<axis>[XYZ])$", col)
                if match:
                    obj_id = match.group("id")
                    axis = match.group("axis")
                    
                    # Filter out Velocity if it has _V_X or _Vx pattern?
                    # Analysis output usually has _Vx, _Vy.
                    # If the regex is _[XYZ], it matches _X.
                    # If velocity is _Vx, it won't match _X (unless x is uppercase).
                    # Let's assume Position columns end in _X, _Y, _Z.
                    
                    if obj_id not in objects_map:
                        objects_map[obj_id] = {}
                    objects_map[obj_id][axis] = col

            # 4. Construct Long Format DataFrame
            # Target columns: Frame, Time, object_id, pos_x, pos_y, pos_z
            
            long_rows = []
            
            # We iterate over each object and extract its XYZ columns + Time/Frame
            # This might be slow for huge files, but for analysis results it's okay.
            # Better approach: pd.wide_to_long?
            # wide_to_long requires consistent stubs.
            # Our stubs are the object IDs.
            
            # Let's try melting or stacking.
            # But we have X, Y, Z separate.
            
            # Strategy:
            # 1. Rename columns to {id}_x, {id}_y, {id}_z (lowercase axis for wide_to_long)
            # 2. Use pd.wide_to_long
            
            rename_dict = {}
            valid_objects = []
            
            for obj_id, axes in objects_map.items():
                if 'X' in axes and 'Y' in axes and 'Z' in axes:
                    rename_dict[axes['X']] = f"{obj_id}_pos_x"
                    rename_dict[axes['Y']] = f"{obj_id}_pos_y"
                    rename_dict[axes['Z']] = f"{obj_id}_pos_z"
                    valid_objects.append(obj_id)
            
            if not valid_objects:
                print("[ERROR] No valid 3D objects (XYZ) found in CSV.")
                return False
                
            # Create a subset with only relevant columns
            cols_to_keep = [TimeCols.FRAME, TimeCols.TIME] + list(rename_dict.keys())
            # Handle case where Time might be missing if we generated Frame
            if TimeCols.TIME not in df.columns:
                 cols_to_keep.remove(TimeCols.TIME)
                 
            df_subset = df[cols_to_keep].rename(columns=rename_dict)
            
            # Now columns are Frame, Time, C1_pos_x, C1_pos_y, ...
            
            # wide_to_long
            # stubnames=['C1', 'C2'...] NO.
            # stubnames should be 'pos_x', 'pos_y', 'pos_z' ?? No.
            # We want one row per object.
            # wide_to_long(df, stubnames=['pos_x', 'pos_y', 'pos_z'], i='Frame', j='object_id', sep='_', suffix='.+')
            # This expects C1_pos_x -> object_id=C1
            # But our rename made it {obj_id}_pos_x.
            # So suffix is the obj_id? No, suffix is usually at the end.
            # Let's rename to pos_x_{obj_id}
            
            rename_dict_2 = {}
            for obj_id in valid_objects:
                rename_dict_2[f"{obj_id}_pos_x"] = f"pos_x_{obj_id}"
                rename_dict_2[f"{obj_id}_pos_y"] = f"pos_y_{obj_id}"
                rename_dict_2[f"{obj_id}_pos_z"] = f"pos_z_{obj_id}"
            
            df_subset = df_subset.rename(columns=rename_dict_2)
            
            # Now columns: pos_x_C1, pos_y_C1...
            # wide_to_long(df, stubnames=['pos_x', 'pos_y', 'pos_z'], i=[Frame, Time], j='object_id', sep='_', suffix='.+')
            
            id_vars = [TimeCols.FRAME]
            if TimeCols.TIME in df_subset.columns:
                id_vars.append(TimeCols.TIME)
                
            df_long = pd.wide_to_long(
                df_subset, 
                stubnames=['pos_x', 'pos_y', 'pos_z'], 
                i=id_vars, 
                j=config.DF_OBJECT_ID, 
                sep='_', 
                suffix='.+',
            )
            
            df_long = df_long.reset_index()
            
            # Ensure column names match config
            # config.DF_POS_X is RigidBodyCols.POS_X ('RigidBody_Position_X')
            # But wide_to_long produced 'pos_x'.
            # We need to rename 'pos_x' -> config.DF_POS_X
            
            df_long.rename(columns={
                'pos_x': config.DF_POS_X,
                'pos_y': config.DF_POS_Y,
                'pos_z': config.DF_POS_Z
            }, inplace=True)

            # --- Finalize Data Handler State ---
            self.visualization_dataframe = df_long
            self.n_frames = int(df_long[config.DF_FRAME].max() + 1)
            self.object_ids = sorted(df_long[config.DF_OBJECT_ID].unique())

            print(f"Successfully loaded analysis result: {filepath}")
            print(f"  - Frames: {self.n_frames}")
            print(f"  - Objects: {len(self.object_ids)}")
            return True

        except Exception as e:
            print(f"An error occurred while loading analysis result: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_frame_data(self, frame_number: int) -> pd.DataFrame | None:
        if self.visualization_dataframe is None: return None
        return self.visualization_dataframe[self.visualization_dataframe[config.DF_FRAME] == frame_number]

    def get_object_timeseries(self, object_id: str) -> pd.DataFrame | None:
        if self.visualization_dataframe is None: return None
        return self.visualization_dataframe[self.visualization_dataframe[config.DF_OBJECT_ID] == object_id]

    def get_object_ids(self) -> list[str]:
        """Returns the sorted list of unique object IDs."""
        return self.object_ids
