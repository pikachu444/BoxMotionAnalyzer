import pandas as pd
import csv
from src.config.data_columns import TimeCols, RawMarkerCols, RigidBodyCols, DisplayNames

class DataLoader:
    def load_csv(self, filepath: str) -> tuple[dict[str, list[str]], pd.DataFrame]:
        """
        원본 CSV 파일을 읽어, 헤더 정보와 원본 데이터 DataFrame을 반환합니다.
        """
        try:
            with open(filepath, mode='r', encoding='utf-8-sig') as infile:
                lines = infile.readlines()
        except FileNotFoundError:
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {filepath}")

        if len(lines) < 8:
            raise ValueError("CSV 파일에 헤더 정보(최소 7줄)와 데이터(최소 1줄)가 부족합니다.")

        header_info = {}
        header_lines = [line.strip().split(',') for line in lines[2:8]]
        max_len = max(len(line) for line in header_lines)
        padded_headers = [[item.strip() for item in line] + [''] * (max_len - len(line)) for line in header_lines]
        header_keys = ['type', 'name', 'id', 'parent', 'category', 'component']
        for i, key in enumerate(header_keys):
            header_info[key] = padded_headers[i]

        component_header = header_info['component']
        data_lines_raw = lines[8:]
        reader = csv.reader(data_lines_raw)
        data_as_list = list(reader)

        if not data_as_list:
            return header_info, pd.DataFrame()

        num_columns = max_len
        df_cols = component_header[:num_columns]
        df_cols += [f'col_{i}' for i in range(len(df_cols), num_columns)]
        raw_df = pd.DataFrame(data_as_list)

        if raw_df.shape[1] < num_columns:
            for i in range(raw_df.shape[1], num_columns):
                raw_df[i] = pd.NA
        raw_df.columns = df_cols

        if len(raw_df.columns) > 1:
            rename_map = {raw_df.columns[0]: TimeCols.FRAME, raw_df.columns[1]: TimeCols.TIME}
            raw_df.rename(columns=rename_map, inplace=True)

        print(f"[DataLoader INFO] CSV loaded. Headers parsed, and {len(raw_df)} data rows prepared for Parser.")
        header_info['component'] = component_header
        return header_info, raw_df

    def load_result_csv(self, filepath: str) -> pd.DataFrame:
        """
        분석 완료 후 Export된, 멀티헤더를 가진 결과 CSV 파일을 읽어 DataFrame으로 반환합니다.
        """
        try:
            # 멀티헤더(3줄)를 올바르게 읽기 위해 header=[0, 1, 2] 옵션을 사용합니다.
            df = pd.read_csv(filepath, header=[0, 1, 2])
            print(f"[DataLoader INFO] Result CSV loaded successfully from {filepath}")
            return df
        except FileNotFoundError:
            raise FileNotFoundError(f"결과 파일을 찾을 수 없습니다: {filepath}")
        except Exception as e:
            raise ValueError(f"결과 파일을 읽는 중 오류가 발생했습니다: {e}")

    def get_plottable_targets(self, processed_df: pd.DataFrame) -> list[str]:
        """
        파싱이 완료된 "wide-format" DataFrame에서 플로팅할 대상의 '표시용 이름' 목록을 생성합니다.
        """
        if processed_df is None or processed_df.empty:
            return []

        base_names = set()
        for col in processed_df.columns:
            if col.endswith((RawMarkerCols.X_SUFFIX, RawMarkerCols.Y_SUFFIX, RawMarkerCols.Z_SUFFIX)):
                base_name = col.rsplit('_', 1)[0]
                base_names.add(base_name)

        final_targets = []
        if RigidBodyCols.BASE_NAME in base_names:
            final_targets.append(DisplayNames.RB_CENTER)
            base_names.remove(RigidBodyCols.BASE_NAME)

        marker_targets = []
        for name in sorted(list(base_names)):
            if ':' in name:
                marker_targets.append(name)
            else:
                marker_targets.append(f"{DisplayNames.MARKER_PREFIX}{name}")

        final_targets.extend(marker_targets)
        return final_targets
