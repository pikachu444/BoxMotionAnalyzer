import pandas as pd
import numpy as np

from src.config import config_visualization as config
from src.config.data_columns import HeaderL1, HeaderL2, HeaderL3


class DataHandler:
    def __init__(self):
        self.visualization_dataframe = None
        self.n_frames = 0
        self.object_ids = []
        self.entity_groups = {
            config.ENTITY_TYPE_COM: [],
            config.ENTITY_TYPE_CORNER: [],
            config.ENTITY_TYPE_MARKER: [],
        }
        self.entity_type_map = {}

    def load_analysis_result(self, filepath: str) -> bool:
        """
        Loads the BoxMotionAnalyzer exported multi-header CSV and transforms it
        into the long-format DataFrame consumed by the visualization GUI.
        """
        try:
            df = pd.read_csv(filepath, header=[0, 1, 2])

            frames = self._extract_frames(df)
            times = self._extract_times(df)
            entity_specs = self._build_entity_specs(df.columns)
            if not entity_specs:
                print("[ERROR] No visualization entities with position data found.")
                return False

            long_data_list = []
            for entity_id, entity_type, source_object_id in entity_specs:
                entity_df = self._build_entity_dataframe(
                    df,
                    frames=frames,
                    times=times,
                    entity_id=entity_id,
                    entity_type=entity_type,
                    source_object_id=source_object_id,
                )
                if entity_df is not None:
                    long_data_list.append(entity_df)

            if not long_data_list:
                print("[ERROR] Failed to build visualization rows from exported CSV.")
                return False

            self.visualization_dataframe = pd.concat(long_data_list, ignore_index=True)
            self.n_frames = int(self.visualization_dataframe[config.DF_FRAME].max() + 1)
            self.entity_groups = self._group_entity_ids(self.visualization_dataframe)
            self.entity_type_map = {
                entity_id: entity_type
                for entity_type, entity_ids in self.entity_groups.items()
                for entity_id in entity_ids
            }
            self.object_ids = self.get_object_ids()

            print(f"Successfully loaded analysis result: {filepath}")
            print(f"  - Frames: {self.n_frames}")
            print(f"  - Entities: {len(self.object_ids)}")
            return True

        except Exception as e:
            print(f"An error occurred while loading analysis result: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _extract_frames(self, df: pd.DataFrame) -> pd.Series:
        col_frame = self._find_column(df.columns, HeaderL1.INFO, HeaderL2.FRAME, HeaderL3.NUM)
        if col_frame is None:
            frames = pd.Series(range(len(df)))
        else:
            frames = df[col_frame]
            if not frames.empty:
                frames = frames - frames.min()
        return frames.reset_index(drop=True)

    def _extract_times(self, df: pd.DataFrame) -> pd.Series:
        col_time = self._find_column(df.columns, HeaderL1.INFO, HeaderL2.TIME, HeaderL3.TIME)
        if col_time is None:
            return pd.Series(np.zeros(len(df)))
        return df[col_time].reset_index(drop=True)

    def _find_column(
        self,
        columns: pd.Index,
        level_1: str,
        level_2: str,
        level_3: str | None = None,
    ):
        for col in columns:
            if col[0] != level_1 or col[1] != level_2:
                continue
            if level_3 is None or col[2] == level_3:
                return col
        return None

    def _series_or_nan(self, df: pd.DataFrame, column, fill_value=np.nan) -> pd.Series:
        if column is None or column not in df.columns:
            return pd.Series(fill_value, index=df.index)
        return df[column]

    def _build_entity_specs(self, columns: pd.Index) -> list[tuple[str, str, str]]:
        position_ids = {
            col[1]
            for col in columns
            if col[0] == HeaderL1.POS and col[2] in {HeaderL3.P_TX, HeaderL3.P_TY, HeaderL3.P_TZ}
        }

        specs = []
        has_com = HeaderL2.COM in position_ids
        has_rigid_body = HeaderL2.RB in position_ids
        if has_com or has_rigid_body:
            source_id = HeaderL2.COM if has_com else HeaderL2.RB
            specs.append((config.ENTITY_ID_COM, config.ENTITY_TYPE_COM, source_id))

        corner_ids = sorted(entity_id for entity_id in position_ids if config.is_corner_entity(entity_id))
        specs.extend(
            (entity_id, config.ENTITY_TYPE_CORNER, entity_id)
            for entity_id in corner_ids
        )

        excluded_ids = {HeaderL2.COM, HeaderL2.RB, *config.BOX_CORNERS_LABELS}
        marker_ids = sorted(entity_id for entity_id in position_ids if entity_id not in excluded_ids)
        specs.extend(
            (entity_id, config.ENTITY_TYPE_MARKER, entity_id)
            for entity_id in marker_ids
        )
        return specs

    def _build_entity_dataframe(
        self,
        df: pd.DataFrame,
        *,
        frames: pd.Series,
        times: pd.Series,
        entity_id: str,
        entity_type: str,
        source_object_id: str,
    ) -> pd.DataFrame | None:
        pos_x_col = self._find_column(df.columns, HeaderL1.POS, source_object_id, HeaderL3.P_TX)
        pos_y_col = self._find_column(df.columns, HeaderL1.POS, source_object_id, HeaderL3.P_TY)
        pos_z_col = self._find_column(df.columns, HeaderL1.POS, source_object_id, HeaderL3.P_TZ)
        if pos_x_col is None or pos_y_col is None or pos_z_col is None:
            print(f"[WARN] Missing position data for {entity_id}")
            return None

        entity_df = pd.DataFrame()
        entity_df[config.DF_FRAME] = frames
        entity_df[config.DF_TIME] = times
        entity_df[config.DF_ENTITY_ID] = entity_id
        entity_df[config.DF_ENTITY_TYPE] = entity_type
        entity_df[config.DF_SOURCE_OBJECT_ID] = source_object_id

        entity_df[config.DF_POS_GLOBAL_X] = df[pos_x_col]
        entity_df[config.DF_POS_GLOBAL_Y] = df[pos_y_col]
        entity_df[config.DF_POS_GLOBAL_Z] = df[pos_z_col]

        entity_df[config.DF_VEL_GLOBAL_X] = self._series_or_nan(
            df, self._find_column(df.columns, HeaderL1.VEL, source_object_id, HeaderL3.V_TX)
        )
        entity_df[config.DF_VEL_GLOBAL_Y] = self._series_or_nan(
            df, self._find_column(df.columns, HeaderL1.VEL, source_object_id, HeaderL3.V_TY)
        )
        entity_df[config.DF_VEL_GLOBAL_Z] = self._series_or_nan(
            df, self._find_column(df.columns, HeaderL1.VEL, source_object_id, HeaderL3.V_TZ)
        )

        speed_series = self._series_or_nan(
            df, self._find_column(df.columns, HeaderL1.VEL, source_object_id, HeaderL3.V_TNORM)
        )
        if speed_series.isna().all():
            speed_series = np.sqrt(
                entity_df[config.DF_VEL_GLOBAL_X].fillna(0.0) ** 2
                + entity_df[config.DF_VEL_GLOBAL_Y].fillna(0.0) ** 2
                + entity_df[config.DF_VEL_GLOBAL_Z].fillna(0.0) ** 2
            )
            if entity_type == config.ENTITY_TYPE_MARKER:
                speed_series = pd.Series(np.nan, index=df.index)
        entity_df[config.DF_SPEED_GLOBAL] = speed_series

        entity_df[config.DF_VEL_BOX_LOCAL_X] = self._series_or_nan(
            df, self._find_column(df.columns, HeaderL1.VEL, source_object_id, HeaderL3.V_TX_ANA)
        )
        entity_df[config.DF_VEL_BOX_LOCAL_Y] = self._series_or_nan(
            df, self._find_column(df.columns, HeaderL1.VEL, source_object_id, HeaderL3.V_TY_ANA)
        )
        entity_df[config.DF_VEL_BOX_LOCAL_Z] = self._series_or_nan(
            df, self._find_column(df.columns, HeaderL1.VEL, source_object_id, HeaderL3.V_TZ_ANA)
        )

        if entity_type != config.ENTITY_TYPE_COM:
            entity_df[config.DF_VEL_BOX_LOCAL_X] = np.nan
            entity_df[config.DF_VEL_BOX_LOCAL_Y] = np.nan
            entity_df[config.DF_VEL_BOX_LOCAL_Z] = np.nan

        if entity_type == config.ENTITY_TYPE_MARKER:
            entity_df[config.DF_VEL_GLOBAL_X] = np.nan
            entity_df[config.DF_VEL_GLOBAL_Y] = np.nan
            entity_df[config.DF_VEL_GLOBAL_Z] = np.nan
            entity_df[config.DF_SPEED_GLOBAL] = np.nan

        return entity_df

    def _group_entity_ids(self, df: pd.DataFrame) -> dict[str, list[str]]:
        if df.empty:
            return {
                config.ENTITY_TYPE_COM: [],
                config.ENTITY_TYPE_CORNER: [],
                config.ENTITY_TYPE_MARKER: [],
            }

        groups = {}
        for entity_type in (
            config.ENTITY_TYPE_COM,
            config.ENTITY_TYPE_CORNER,
            config.ENTITY_TYPE_MARKER,
        ):
            entity_ids = (
                df.loc[df[config.DF_ENTITY_TYPE] == entity_type, config.DF_ENTITY_ID]
                .drop_duplicates()
                .tolist()
            )
            groups[entity_type] = entity_ids
        return groups

    def get_frame_data(self, frame_number: int) -> pd.DataFrame | None:
        if self.visualization_dataframe is None:
            return None
        return self.visualization_dataframe[self.visualization_dataframe[config.DF_FRAME] == frame_number]

    def get_entity_timeseries(self, entity_id: str) -> pd.DataFrame | None:
        if self.visualization_dataframe is None:
            return None
        return self.visualization_dataframe[self.visualization_dataframe[config.DF_ENTITY_ID] == entity_id]

    def get_object_timeseries(self, object_id: str) -> pd.DataFrame | None:
        return self.get_entity_timeseries(object_id)

    def get_object_ids(self) -> list[str]:
        ordered_ids = []
        for entity_type in (
            config.ENTITY_TYPE_COM,
            config.ENTITY_TYPE_CORNER,
            config.ENTITY_TYPE_MARKER,
        ):
            ordered_ids.extend(self.entity_groups.get(entity_type, []))
        return ordered_ids

    def get_entities_by_type(self) -> dict[str, list[str]]:
        return {
            entity_type: list(entity_ids)
            for entity_type, entity_ids in self.entity_groups.items()
        }

    def get_entity_type(self, entity_id: str) -> str | None:
        return self.entity_type_map.get(entity_id)

    def get_entity_ids_by_type(self, entity_type: str) -> list[str]:
        return list(self.entity_groups.get(entity_type, []))
