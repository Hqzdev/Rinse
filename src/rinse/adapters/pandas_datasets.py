import json
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from rinse.adapters.dataset_files import DatasetFileError, DatasetFormatDetector, DatasetPath
from rinse.domain.entities import Dataset
from rinse.domain.value_objects import CellValue, ColumnName, DatasetFormat, DatasetReference
from rinse.ports.datasets import DatasetReader, DatasetWriter


class PandasDatasetMapper:
    def to_dataset(self, frame: pd.DataFrame) -> Dataset:
        columns = tuple(ColumnName(str(column)) for column in frame.columns)
        rows = tuple(
            {
                str(column): self.to_cell_value(value)
                for column, value in row.items()
            }
            for row in frame.to_dict(orient="records")
        )
        return Dataset(columns=columns, rows=rows)

    def to_frame(self, dataset: Dataset) -> pd.DataFrame:
        return pd.DataFrame(list(dataset.rows), columns=[column.value for column in dataset.columns])

    def to_cell_value(self, value: Any) -> CellValue:
        if pd.isna(value):
            return None
        if hasattr(value, "item"):
            value = value.item()
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)


class PandasDatasetReader(DatasetReader):
    def __init__(
        self,
        detector: Optional[DatasetFormatDetector] = None,
        mapper: Optional[PandasDatasetMapper] = None,
        path_resolver: Optional[DatasetPath] = None,
    ) -> None:
        self.detector = detector or DatasetFormatDetector()
        self.mapper = mapper or PandasDatasetMapper()
        self.path_resolver = path_resolver or DatasetPath()

    def read(self, source: DatasetReference) -> Dataset:
        path = self.path_resolver.resolve(source)
        dataset_format = self.detector.detect(source)
        try:
            if dataset_format == DatasetFormat.CSV:
                return self.mapper.to_dataset(pd.read_csv(path))
            if dataset_format == DatasetFormat.XLSX:
                return self.mapper.to_dataset(pd.read_excel(path, sheet_name=0))
            if dataset_format == DatasetFormat.JSON:
                return self.mapper.to_dataset(pd.read_json(path))
        except ValueError as error:
            raise DatasetFileError(f"Could not read dataset file: {source.location}") from error
        raise DatasetFileError(f"Cannot read dataset format: {dataset_format.value}")


class PandasDatasetWriter(DatasetWriter):
    def __init__(
        self,
        detector: Optional[DatasetFormatDetector] = None,
        mapper: Optional[PandasDatasetMapper] = None,
    ) -> None:
        self.detector = detector or DatasetFormatDetector()
        self.mapper = mapper or PandasDatasetMapper()

    def write(self, dataset: Dataset, target: DatasetReference) -> DatasetReference:
        dataset_format = self.detector.detect(target)
        path = Path(target.location)
        path.parent.mkdir(parents=True, exist_ok=True)
        frame = self.mapper.to_frame(dataset)
        if dataset_format == DatasetFormat.CSV:
            frame.to_csv(path, index=False)
            return target
        if dataset_format == DatasetFormat.XLSX:
            frame.to_excel(path, index=False, engine="openpyxl")
            return target
        if dataset_format == DatasetFormat.JSON:
            records = frame.to_dict(orient="records")
            path.write_text(json.dumps(records, ensure_ascii=False, indent=2))
            return target
        raise DatasetFileError(f"Cannot write dataset format: {dataset_format.value}")
