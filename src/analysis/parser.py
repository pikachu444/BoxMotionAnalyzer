import pandas as pd
from src.config.data_columns import TimeCols, RawMarkerCols, RigidBodyCols, FACE_PREFIX_TO_INFO

class Parser:
    """
    "long-format"의 원본 DataFrame을 분석에 용이한 "wide-format"으로 변환합니다.
    AlignBoxInputGenbyExperiment.py 스크립트의 핵심 로직을 클래스 형태로 이식한 것입니다.
    """

    def __init__(self, face_prefix_map: dict[str, str]):
        """
        Parser를 초기화합니다.

        Args:
            face_prefix_map (dict[str, str]): 마커 접두사와 면(Face) 정보를 매핑하는 딕셔너리.
        """
        self.face_prefix_map = face_prefix_map

    def process(self, header_info: dict[str, list[str]], raw_df: pd.DataFrame) -> pd.DataFrame:
        """
        원본 DataFrame을 파싱하여 wide-format DataFrame으로 변환합니다.
        """
        if raw_df.empty:
            return pd.DataFrame()

        # Prepare header data for merging
        headers = pd.DataFrame({
            'col_index': range(len(header_info['type'])),
            'type': header_info['type'],
            'name': header_info['name'],
            'parent': header_info['parent'],
            'category': header_info['category'],
            'component': header_info['component']
        })

        # Melt the raw_df to long format
        id_vars = [TimeCols.FRAME, TimeCols.TIME]
        value_vars = [col for col in raw_df.columns if col not in id_vars]
        long_df = pd.melt(raw_df, id_vars=id_vars, value_vars=value_vars, var_name='original_col', value_name='value')

        # Extract column index from original_col name
        long_df['col_index'] = long_df['original_col'].str.extract(r'col_(\d+)').astype(int)

        # Merge with headers
        merged_df = pd.merge(long_df, headers, on='col_index')

        # Filter for Rigid Body Markers
        marker_df = merged_df[
            (merged_df['type'] == 'Rigid Body Marker') &
            (merged_df['parent'].notna()) &
            (merged_df['name'].str.contains(':')) &
            (merged_df['category'] == 'Position')
        ].copy()

        # Extract marker identifier
        marker_df['marker_id'] = marker_df['name'].apply(lambda x: x.split(':', 1)[1].replace(" ", "_"))

        # Pivot to wide format
        pivoted = marker_df.pivot_table(
            index=[TimeCols.FRAME, TimeCols.TIME],
            columns=['marker_id', 'component'],
            values='value',
            aggfunc='first'
        ).reset_index()

        # Flatten multi-level columns
        pivoted.columns = [f"{col[0]}_{col[1]}" if col[1] else col[0] for col in pivoted.columns]

        # Add FaceInfo
        for marker_id in marker_df['marker_id'].unique():
            prefix_for_face = ""
            if marker_id.startswith("FA"):
                prefix_for_face = "FA"
            elif marker_id.startswith("BA"):
                prefix_for_face = "BA"
            elif marker_id:
                prefix_for_face = marker_id[0]

            face_info = self.face_prefix_map.get(prefix_for_face.upper(), "")
            pivoted[f"{marker_id}_FaceInfo"] = face_info

        # Reorder columns
        final_cols = [TimeCols.FRAME, TimeCols.TIME]
        for marker_id in sorted(marker_df['marker_id'].unique()):
            final_cols.extend([
                f"{marker_id}_FaceInfo",
                f"{marker_id}_X",
                f"{marker_id}_Y",
                f"{marker_id}_Z"
            ])

        final_df = pivoted[[col for col in final_cols if col in pivoted.columns]]
        final_df.rename(columns={TimeCols.FRAME: 'FrameNumber', TimeCols.TIME: 'Time'}, inplace=True)

        # Convert data types
        final_df['Time'] = pd.to_numeric(final_df['Time'])
        coord_cols = [col for col in final_df.columns if col.endswith(('_X', '_Y', '_Z'))]
        final_df[coord_cols] = final_df[coord_cols].apply(pd.to_numeric)

        final_df.set_index('Time', inplace=True)

        return final_df
