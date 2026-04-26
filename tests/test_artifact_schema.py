import unittest
import inspect

import extractor
import extractor.artifact_schema as artifact_schema
from extractor import validate_artifact as package_validate_artifact
from extractor.artifact_schema import validate_artifact, validate_artifact_object
from extractor.errors import AppError, SCHEMA_VALIDATION_ERROR


class TestArtifactSchema(unittest.TestCase):
    def test_import_artifact_schema_does_not_import_cli(self) -> None:
        source = inspect.getsource(artifact_schema)
        self.assertNotIn("extractor.cli", source)

    def test_valid_artifact_passes(self) -> None:
        artifact = {"status": "PASS", "exit_code": 0, "stdout": "ok\n", "stderr": ""}
        self.assertEqual(validate_artifact_object(artifact), artifact)

    def test_validate_artifact_public_api_passes_for_valid_artifact(self) -> None:
        artifact = {"status": "PASS", "exit_code": 0, "stdout": "ok\n", "stderr": ""}
        result = validate_artifact(artifact)
        self.assertEqual(result, artifact)
        self.assertEqual(result["stdout"], "ok\n")

    def test_package_level_validate_artifact_import_surface(self) -> None:
        artifact = {"status": "PASS", "exit_code": 0, "stdout": "ok\n", "stderr": ""}
        result = package_validate_artifact(artifact)
        self.assertEqual(result, artifact)

    def test_direct_module_import_path_still_works(self) -> None:
        artifact = {"status": "PASS", "exit_code": 0, "stdout": "ok\n", "stderr": ""}
        result = artifact_schema.validate_artifact(artifact)
        self.assertEqual(result, artifact)

    def test_package_and_module_exports_are_same_callable(self) -> None:
        self.assertIs(package_validate_artifact, artifact_schema.validate_artifact)

    def test_validate_artifact_is_in_package_all(self) -> None:
        self.assertIn("validate_artifact", extractor.__all__)

    def test_missing_required_field_fails(self) -> None:
        artifact = {"status": "PASS", "exit_code": 0, "stdout": "ok\n"}
        with self.assertRaises(AppError) as ctx:
            validate_artifact_object(artifact)
        self.assertEqual(ctx.exception.error_type, SCHEMA_VALIDATION_ERROR)
        self.assertEqual(ctx.exception.message, "Artifact has invalid fields")

    def test_validate_artifact_public_api_fails_deterministically(self) -> None:
        artifact = {"status": "PASS", "exit_code": 0, "stdout": "ok\n"}
        with self.assertRaises(AppError) as ctx:
            validate_artifact(artifact)
        self.assertEqual(ctx.exception.error_type, SCHEMA_VALIDATION_ERROR)
        self.assertEqual(ctx.exception.message, "Artifact has invalid fields")

    def test_invalid_field_value_or_type_fails(self) -> None:
        artifact = {"status": "UNKNOWN", "exit_code": 0, "stdout": "ok\n", "stderr": ""}
        with self.assertRaises(AppError) as ctx:
            validate_artifact_object(artifact)
        self.assertEqual(ctx.exception.error_type, SCHEMA_VALIDATION_ERROR)
        self.assertEqual(ctx.exception.message, "Artifact has invalid status")

    def test_public_api_matches_existing_validation_behavior(self) -> None:
        artifact = {"status": "PASS", "exit_code": "0", "stdout": "ok\n", "stderr": ""}
        with self.assertRaises(AppError) as object_err:
            validate_artifact_object(artifact)
        with self.assertRaises(AppError) as public_err:
            validate_artifact(artifact)
        self.assertEqual(public_err.exception.error_type, object_err.exception.error_type)
        self.assertEqual(public_err.exception.message, object_err.exception.message)


if __name__ == "__main__":
    unittest.main()
