import pandas as pd

class DataValidator:
    """
    데이터 분석 전 데이터의 유효성을 검증하는 클래스입니다.
    """

    @staticmethod
    def validate_required_columns(df: pd.DataFrame, required_columns: list) -> None:
        """
        데이터프레임에 필수 컬럼이 모두 존재하는지 확인합니다.
        
        Args:
            df (pd.DataFrame): 검증할 데이터프레임
            required_columns (list): 필수 컬럼 이름 리스트

        Raises:
            ValueError: 필수 컬럼이 하나라도 누락된 경우
        """
        if df is None or df.empty:
            raise ValueError("Data is empty or None.")

        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

    @staticmethod
    def validate_data_sufficiency(df: pd.DataFrame, min_rows: int = 10) -> None:
        """
        데이터프레임이 분석에 충분한 행(row)을 가지고 있는지 확인합니다.

        Args:
            df (pd.DataFrame): 검증할 데이터프레임
            min_rows (int): 최소 요구 행 수 (기본값: 10)

        Raises:
            ValueError: 데이터 행 수가 부족한 경우
        """
        if df is None:
            raise ValueError("Data is None.")
        
        if len(df) < min_rows:
            raise ValueError(f"Data has insufficient rows for analysis. (Required: {min_rows}, Actual: {len(df)})")
