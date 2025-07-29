import pandas as pd
import csv
from src.config.data_columns import TimeCols, RawMarkerCols

class DataLoader:
    def load_csv(self, filepath: str) -> tuple[dict[str, list[str]], pd.DataFrame]:
        """
        CSV 파일을 읽어, 헤더 정보와 원본 데이터 DataFrame을 반환합니다.
        이 메서드는 최소한의 파싱만 수행하며, 복잡한 데이터 변환은 Parser 모듈의 책임입니다.

        Args:
            filepath (str): 읽어올 CSV 파일의 경로.

        Returns:
            Tuple[Dict[str, List[str]], pd.DataFrame]:
                - 헤더 정보를 담은 딕셔너리.
                - 원본 데이터(8번째 줄부터)를 담은 DataFrame.
        """
        try:
            with open(filepath, mode='r', encoding='utf-8-sig') as infile:
                lines = infile.readlines()
        except FileNotFoundError:
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {filepath}")

        if len(lines) < 8:
            raise ValueError("CSV 파일에 헤더 정보(최소 7줄)와 데이터(최소 1줄)가 부족합니다.")

        # 1. 헤더 정보 파싱 (상위 7줄)
        header_info = {}
        header_lines = [line.strip().split(',') for line in lines[2:8]]

        max_len = max(len(line) for line in header_lines)

        padded_headers = [[item.strip() for item in line] + [''] * (max_len - len(line)) for line in header_lines]

        header_keys = ['type', 'name', 'id', 'parent', 'category', 'component']
        for i, key in enumerate(header_keys):
            header_info[key] = padded_headers[i]

        component_header = header_info['component']

        # 2. 원본 데이터 DataFrame 생성
        data_lines_raw = lines[8:]

        reader = csv.reader(data_lines_raw)
        data_as_list = list(reader)

        if not data_as_list:
            return header_info, pd.DataFrame()

        # 데이터프레임 생성
        num_columns = max_len

        # 컬럼명을 component_header에서 가져오되, 길이가 부족하면 col_X 형식으로 채움
        df_cols = component_header[:num_columns]
        df_cols += [f'col_{i}' for i in range(len(df_cols), num_columns)]
        raw_df = pd.DataFrame(data_as_list)
        if raw_df.shape[1] < num_columns:
            # Add missing columns with NaN
            for i in range(raw_df.shape[1], num_columns):
                raw_df[i] = pd.NA
        raw_df.columns = df_cols

        # 첫 두 컬럼에 대한 기본 이름 부여 (Frame, Time)
        # 원본 데이터에 Frame, Time 컬럼이 없을 수 있으므로, 예외 처리 추가
        if len(raw_df.columns) > 1:
            rename_map = {raw_df.columns[0]: TimeCols.FRAME, raw_df.columns[1]: TimeCols.TIME}
            raw_df.rename(columns=rename_map, inplace=True)

        print(f"[DataLoader INFO] CSV loaded. Headers parsed, and {len(raw_df)} data rows prepared for Parser.")
        header_info['component'] = component_header
        return header_info, raw_df

    def get_plottable_targets(self, processed_df: pd.DataFrame) -> list[str]:
        """
        파싱이 완료된 "wide-format" DataFrame에서 플로팅할 대상 목록을 추출합니다.
        """
        if processed_df is None or processed_df.empty:
            return []

        targets = set()
        for col in processed_df.columns:
            if col.endswith((RawMarkerCols.X_SUFFIX, RawMarkerCols.Y_SUFFIX, RawMarkerCols.Z_SUFFIX)):
                base_name = col.rsplit('_', 1)[0]
                targets.add(base_name)

        final_targets = []
        for name in sorted(list(targets)):
            if ':' in name:
                final_targets.append(name)
            else:
                final_targets.append(f"{name} (Rigid Body)")

        return final_targets
