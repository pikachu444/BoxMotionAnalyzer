import pandas as pd
from src.config.data_columns import TimeCols, RawMarkerCols, RigidBodyCols

class Parser:
    """
    "long-format"의 원본 DataFrame을 분석에 용이한 "wide-format"으로 변환합니다.
    AlignBoxInputGenbyExperiment.py 스크립트의 핵심 로직을 클래스 형태로 이식한 것입니다.
    """

    def __init__(self, face_prefix_map: dict[str, str]):
        self.face_prefix_map = face_prefix_map

    def process(self, header_info: dict[str, list[str]], raw_df: pd.DataFrame) -> pd.DataFrame:
        if raw_df.empty:
            return pd.DataFrame()

        type_header = header_info.get('type', [])
        name_header = header_info.get('name', [])
        parent_header = header_info.get('parent', [])
        category_header = header_info.get('category', [])
        component_header = header_info.get('component', [])

        processed_frames_data = []
        all_marker_identifiers = set()

        header_len = len(type_header)

        # 1. Processable한 모든 식별자(마커 및 Rigid Body)를 미리 수집
        for i in range(header_len - 2):
            # Rigid Body Marker 식별
            if (type_header[i] == "Rigid Body Marker" and parent_header[i] and
                ':' in name_header[i] and category_header[i] == "Position" and
                component_header[i].upper() == 'X'):
                name_parts = name_header[i].split(':', 1)
                if len(name_parts) > 1 and name_parts[1]:
                    all_marker_identifiers.add(name_parts[1].replace(" ", "_"))

            # Rigid Body Position 식별
            if (type_header[i] == "Rigid Body" and category_header[i] == "Position" and
                component_header[i].upper() == 'X'):
                all_marker_identifiers.add(RigidBodyCols.BASE_NAME)

        # 2. 각 프레임의 데이터 파싱
        for index, row in raw_df.iterrows():
            current_frame_output_dict = {
                TimeCols.FRAME: row.get(TimeCols.FRAME),
                TimeCols.TIME: row.get(TimeCols.TIME)
            }

            for i in range(header_len - 2):
                # Rigid Body Marker 처리
                if (type_header[i] == "Rigid Body Marker" and parent_header[i] and
                    ':' in name_header[i] and category_header[i] == "Position" and
                    component_header[i].upper() == 'X' and
                    category_header[i+1] == "Position" and component_header[i+1].upper() == 'Y' and
                    category_header[i+2] == "Position" and component_header[i+2].upper() == 'Z'):

                    name_parts = name_header[i].split(':', 1)
                    marker_identifier = name_parts[1].replace(" ", "_")

                    x_val, y_val, z_val = row.iloc[i], row.iloc[i+1], row.iloc[i+2]
                    if pd.isna(x_val) or pd.isna(y_val) or pd.isna(z_val): continue

                    prefix = ""
                    if marker_identifier.startswith("FA"): prefix = "FA"
                    elif marker_identifier.startswith("BA"): prefix = "BA"
                    elif marker_identifier: prefix = marker_identifier[0]

                    face_info = self.face_prefix_map.get(prefix.upper(), "")

                    current_frame_output_dict[f"{marker_identifier}_FaceInfo"] = face_info
                    current_frame_output_dict[f"{marker_identifier}_X"] = x_val
                    current_frame_output_dict[f"{marker_identifier}_Y"] = y_val
                    current_frame_output_dict[f"{marker_identifier}_Z"] = z_val

                # Rigid Body Position 처리
                if (type_header[i] == "Rigid Body" and category_header[i] == "Position" and
                    component_header[i].upper() == 'X' and
                    category_header[i+1] == "Position" and component_header[i+1].upper() == 'Y' and
                    category_header[i+2] == "Position" and component_header[i+2].upper() == 'Z'):

                    x_val, y_val, z_val = row.iloc[i], row.iloc[i+1], row.iloc[i+2]
                    if pd.isna(x_val) or pd.isna(y_val) or pd.isna(z_val): continue

                    current_frame_output_dict[RigidBodyCols.POS_X] = x_val
                    current_frame_output_dict[RigidBodyCols.POS_Y] = y_val
                    current_frame_output_dict[RigidBodyCols.POS_Z] = z_val

            processed_frames_data.append(current_frame_output_dict)

        if not processed_frames_data:
            return pd.DataFrame()

        # 3. 최종 DataFrame 생성
        final_df = pd.DataFrame(processed_frames_data)

        # 데이터 타입 변환
        final_df[TimeCols.TIME] = pd.to_numeric(final_df[TimeCols.TIME], errors='coerce')
        coord_cols = [col for col in final_df.columns if col.endswith(('_X', '_Y', '_Z'))]
        if coord_cols:
            final_df[coord_cols] = final_df[coord_cols].apply(pd.to_numeric, errors='coerce')

        final_df = final_df.dropna(subset=[TimeCols.TIME])
        final_df.set_index(TimeCols.TIME, inplace=True)

        return final_df
