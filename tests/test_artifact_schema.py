import unittest

from extractor.artifact_schema import validate_artifact_object
from extractor.errors import AppError, SCHEMA_VALIDATION_ERROR


class TestArtifactSchema(unittest.TestCase):
    def test_valid_artifact_passes(self) -> None:
        artifact = {"status": "PASS", "exit_code": 0, "stdout": "ok\n", "stderr": ""}
        self.assertEqual(validate_artifact_object(artifact), artifact)

    def test_missing_required_field_fails(self) -> None:
        artifact = {"status": "PASS", "exit_code": 0, "stdout": "ok\n"}
        with self.assertRaises(AppError) as ctx:
            validate_artifact_object(artifact)
        self.assertEqual(ctx.exception.error_type, SCHEMA_VALIDATION_ERROR)
        self.assertEqual(ctx.exception.message, "Artifact has invalid fields")

    def test_invalid_field_value_or_type_fails(self) -> None:
        artifact = {"status": "UNKNOWN", "exit_code": 0, "stdout": "ok\n", "stderr": ""}
        with self.assertRaises(AppError) as ctx:
            validate_artifact_object(artifact)
        self.assertEqual(ctx.exception.error_type, SCHEMA_VALIDATION_ERROR)
        self.assertEqual(ctx.exception.message, "Artifact has invalid status")


if __name__ == "__main__":
    unittest.main()
