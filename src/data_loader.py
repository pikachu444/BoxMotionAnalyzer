import pandas as pd
import csv
import time

class DataLoader:
    def load_csv(self, filepath: str) -> pd.DataFrame:
        """
        AlignBoxInputGenbyExperiment.py의 순수 Python 로직을 사용하여
        CSV를 파싱하고, 최종적으로 Pandas DataFrame을 반환합니다.
        """
        start_time = time.time()
        try:
            with open(filepath, mode='r', encoding='utf-8-sig') as infile:
                reader = csv.reader(infile)
                lines = list(reader)
        except FileNotFoundError:
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {filepath}")

        if len(lines) < 9:
            raise ValueError("CSV 파일에 헤더 정보가 부족합니다.")

        type_header = [h.strip() for h in lines[2]]
        name_header = [h.strip() for h in lines[3]]
        category_header = [h.strip() for h in lines[6]]

        processed_data = []
        for row_data in lines[8:]:
            if not any(row_data): continue

            try:
                frame_time = float(row_data[1])
            except (ValueError, IndexError):
                continue

            frame_dict = {'Time': frame_time}

            for i in range(len(row_data)):
                if i >= len(category_header) or i >= len(type_header) or i >= len(name_header):
                    continue

                obj_type = type_header[i]
                is_target_type = ('Rigid Body' in obj_type or 'Rigid Body Marker' in obj_type)
                is_position_data = (category_header[i] == 'Position')

                if is_target_type and is_position_data:
                    obj_name = name_header[i]
                    if not obj_name: continue

                    try:
                        if (i + 2) < len(row_data):
                            x_val = float(row_data[i])
                            y_val = float(row_data[i+1])
                            z_val = float(row_data[i+2])

                            frame_dict[f"{obj_name}_X"] = x_val
                            frame_dict[f"{obj_name}_Y"] = y_val
                            frame_dict[f"{obj_name}_Z"] = z_val
                    except (ValueError, IndexError):
                        continue

            processed_data.append(frame_dict)

        if not processed_data:
            return pd.DataFrame()

        df = pd.DataFrame(processed_data)
        df.set_index('Time', inplace=True)

        end_time = time.time()
        print(f"[DataLoader 정보] CSV 파싱 소요 시간: {end_time - start_time:.4f}초")

        return df

    def get_plottable_targets(self, raw_data: pd.DataFrame) -> list[str]:
        if raw_data is None or raw_data.empty:
            return []

        targets = set()
        for col in raw_data.columns:
            base_name = col.rsplit('_', 1)[0]
            targets.add(base_name)

        final_targets = []
        for name in sorted(list(targets)):
            if ':' in name:
                final_targets.append(name)
            else:
                final_targets.append(f"{name} (강체 중심)")

        return final_targets
