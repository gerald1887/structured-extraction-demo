import unittest
import inspect

import extractor
import extractor.artifact_schema as artifact_schema
from extractor import validate_artifact as package_validate_artifact
from extractor.artifact_schema import validate_artifact, validate_artifact_object
from extractor.errors import AppError, SCHEMA_VALIDATION_ERROR


class TestArtifactSchema(unittest.TestCase):
    def test_package_level_validate_artifact_is_callable(self) -> None:
        self.assertTrue(callable(package_validate_artifact))

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

    def test_validate_artifact_happy_path_no_mutation_or_coercion(self) -> None:
        artifact = {"status": "FAIL", "exit_code": 1, "stdout": "", "stderr": "err\n"}
        before = dict(artifact)
        result = validate_artifact(artifact)
        self.assertIs(result, artifact)
        self.assertEqual(artifact, before)
        self.assertIsInstance(result["exit_code"], int)

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

    def test_validate_artifact_invalid_object_raises_stable_app_error(self) -> None:
        with self.assertRaises(AppError) as ctx:
            validate_artifact(["not", "an", "object"])
        self.assertEqual(ctx.exception.error_type, SCHEMA_VALIDATION_ERROR)
        self.assertEqual(ctx.exception.message, "Artifact must be a JSON object")

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

    def test_exit_code_bool_fails_with_exact_error_type_and_message(self) -> None:
        artifact = {"status": "PASS", "exit_code": True, "stdout": "ok\n", "stderr": ""}
        with self.assertRaises(AppError) as ctx:
            validate_artifact(artifact)
        self.assertEqual(ctx.exception.error_type, SCHEMA_VALIDATION_ERROR)
        self.assertEqual(ctx.exception.message, "Artifact exit_code must be int")

    def test_exit_code_out_of_range_fails_with_exact_message(self) -> None:
        artifact = {"status": "PASS", "exit_code": 256, "stdout": "ok\n", "stderr": ""}
        with self.assertRaises(AppError) as ctx:
            validate_artifact_object(artifact)
        self.assertEqual(ctx.exception.error_type, SCHEMA_VALIDATION_ERROR)
        self.assertEqual(ctx.exception.message, "Artifact exit_code must be in range 0-255")

    def test_exit_code_negative_fails_with_exact_error_type_and_message(self) -> None:
        artifact = {"status": "PASS", "exit_code": -1, "stdout": "ok\n", "stderr": ""}
        with self.assertRaises(AppError) as ctx:
            validate_artifact(artifact)
        self.assertEqual(ctx.exception.error_type, SCHEMA_VALIDATION_ERROR)
        self.assertEqual(ctx.exception.message, "Artifact exit_code must be in range 0-255")

    def test_stdout_non_string_fails_with_exact_message(self) -> None:
        artifact = {"status": "PASS", "exit_code": 0, "stdout": 1, "stderr": ""}
        with self.assertRaises(AppError) as ctx:
            validate_artifact_object(artifact)
        self.assertEqual(ctx.exception.error_type, SCHEMA_VALIDATION_ERROR)
        self.assertEqual(ctx.exception.message, "Artifact stdout must be string")

    def test_stderr_non_string_fails_with_exact_message(self) -> None:
        artifact = {"status": "PASS", "exit_code": 0, "stdout": "ok\n", "stderr": 1}
        with self.assertRaises(AppError) as ctx:
            validate_artifact_object(artifact)
        self.assertEqual(ctx.exception.error_type, SCHEMA_VALIDATION_ERROR)
        self.assertEqual(ctx.exception.message, "Artifact stderr must be string")

    def test_boundary_valid_exit_code_255_and_empty_streams(self) -> None:
        artifact = {"status": "ERROR", "exit_code": 255, "stdout": "", "stderr": ""}
        result = validate_artifact(artifact)
        self.assertEqual(result, artifact)

    def test_canonical_external_consumer_contract(self) -> None:
        valid = {"status": "PASS", "exit_code": 0, "stdout": "ok\n", "stderr": ""}
        self.assertEqual(package_validate_artifact(valid), valid)
        invalid = {"status": "PASS", "exit_code": "0", "stdout": "ok\n", "stderr": ""}
        with self.assertRaises(AppError) as ctx:
            package_validate_artifact(invalid)
        self.assertEqual(ctx.exception.error_type, SCHEMA_VALIDATION_ERROR)
        self.assertEqual(ctx.exception.message, "Artifact exit_code must be int")


if __name__ == "__main__":
    unittest.main()
