import pandas as pd
import numpy as np
from src.config import config_visualization as config
from src.config.data_columns import HeaderL1, HeaderL2, HeaderL3

class DataHandler:
    def __init__(self):
        self.visualization_dataframe = None
        self.n_frames = 0
        self.object_ids = []

    def load_analysis_result(self, filepath: str) -> bool:
        """
        Loads the BoxMotionAnalyzer result CSV (Multi-Header) and transforms it
        into the long-format DataFrame expected by the visualizer.
        """
        try:
            # 1. Load CSV with MultiIndex Header
            # header=[0, 1, 2] reads the first 3 rows as headers
            df = pd.read_csv(filepath, header=[0, 1, 2])
            
            # 2. Extract Frame and Time columns
            # We expect them at specific locations based on make_testdata.py and data_columns.py
            # Frame: (Info, Frame, Number)
            # Time: (Info, Time, Time)
            
            col_frame = (HeaderL1.INFO, HeaderL2.FRAME, HeaderL3.NUM)
            col_time = (HeaderL1.INFO, HeaderL2.TIME, HeaderL3.TIME)
            
            # Helper to find column if slightly different (robustness)
            def find_col(target_l1, target_l2):
                for col in df.columns:
                    if col[0] == target_l1 and col[1] == target_l2:
                        return col
                return None

            if col_frame not in df.columns:
                col_frame = find_col(HeaderL1.INFO, HeaderL2.FRAME)
            
            if col_time not in df.columns:
                col_time = find_col(HeaderL1.INFO, HeaderL2.TIME)

            if col_frame is None and col_time is None:
                print("[ERROR] Could not find Frame or Time columns in Multi-Header CSV.")
                return False

            # Extract base series
            if col_frame in df.columns:
                frames = df[col_frame]
            else:
                # Generate frames if missing but time exists
                frames = pd.Series(range(len(df)))
            
            if col_time in df.columns:
                times = df[col_time]
            else:
                times = pd.Series(np.zeros(len(df))) # Should not happen ideally

            # 3. Identify Objects
            # Iterate over Level 2 (Object ID)
            # We filter for columns that have Position data (HeaderL1.POS)
            
            # Get all unique Level 2 keys where Level 1 is Position
            # df.columns is a MultiIndex
            # col is (L1, L2, L3)
            
            object_ids = set()
            for col in df.columns:
                l1, l2, l3 = col
                if l1 == HeaderL1.POS:
                    object_ids.add(l2)
            
            object_ids = sorted(list(object_ids))
            
            if not object_ids:
                print("[ERROR] No objects with Position data found.")
                return False

            # 4. Construct Long-Format DataFrame
            # Target columns: Frame, Time, object_id, pos_x, pos_y, pos_z, vel_x, vel_y, vel_z
            
            long_data_list = []
            
            for obj_id in object_ids:
                # Prepare a DataFrame for this object
                obj_df = pd.DataFrame()
                obj_df[config.DF_FRAME] = frames
                obj_df[config.DF_TIME] = times
                obj_df[config.DF_OBJECT_ID] = obj_id
                
                # Extract Position
                # We expect PX, PY, PZ under (Position, obj_id, ...)
                try:
                    obj_df[config.DF_POS_X] = df[(HeaderL1.POS, obj_id, HeaderL3.PX)]
                    obj_df[config.DF_POS_Y] = df[(HeaderL1.POS, obj_id, HeaderL3.PY)]
                    obj_df[config.DF_POS_Z] = df[(HeaderL1.POS, obj_id, HeaderL3.PZ)]
                except KeyError:
                    # Partial data? Skip or fill NaNs
                    print(f"[WARN] Missing position data for {obj_id}")
                    continue

                # Extract Velocity (Optional but recommended)
                # We expect VX, VY, VZ under (Velocity, obj_id, ...)
                if (HeaderL1.VEL, obj_id, HeaderL3.VX) in df.columns:
                    obj_df[config.DF_VEL_X] = df[(HeaderL1.VEL, obj_id, HeaderL3.VX)]
                    obj_df[config.DF_VEL_Y] = df[(HeaderL1.VEL, obj_id, HeaderL3.VY)]
                    obj_df[config.DF_VEL_Z] = df[(HeaderL1.VEL, obj_id, HeaderL3.VZ)]
                else:
                    obj_df[config.DF_VEL_X] = np.nan
                    obj_df[config.DF_VEL_Y] = np.nan
                    obj_df[config.DF_VEL_Z] = np.nan

                long_data_list.append(obj_df)

            if not long_data_list:
                return False

            self.visualization_dataframe = pd.concat(long_data_list, ignore_index=True)

            # Update state
            self.n_frames = int(self.visualization_dataframe[config.DF_FRAME].max() + 1)
            self.object_ids = object_ids

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
