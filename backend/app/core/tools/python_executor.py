import ast
import sys
from typing import Any

from app.core.logging import logger
from app.core.tools.base import BaseTool, ToolResult

ALLOWED_IMPORTS = {
    "pandas",
    "pd",
    "numpy",
    "np",
    "matplotlib",
    "matplotlib.pyplot",
    "plt",
    "json",
    "math",
    "statistics",
    "collections",
    "datetime",
    "re",
    "typing",
    "itertools",
}


class PythonExecutorTool(BaseTool):
    @property
    def name(self) -> str:
        return "python_executor"

    @property
    def description(self) -> str:
        return (
            "Execute Python code for data analysis, visualization, "
            "and computation. Use this to process data, create charts, "
            "or run statistical analysis."
        )

    async def execute(self, *args: Any, **kwargs: Any) -> ToolResult:
        code = kwargs.get("code", args[0] if args else "")
        timeout = int(kwargs.get("timeout", args[1] if len(args) > 1 else 30))

        try:
            logger.info("Executing Python code with timeout %s seconds", timeout)
            self._validate_code(code)

            stdout, stderr, returncode = self._run_code(code, timeout)

            logger.info(
                "Execution completed (returncode=%s, stderr=%s)",
                returncode,
                bool(stderr),
            )

            success = (returncode == 0) and not stderr
            result_data = {
                "stdout": stdout,
                "stderr": stderr,
                "returncode": returncode,
                "plots": [],
            }

            if success:
                return ToolResult(success=True, data=result_data)
            else:
                return ToolResult(success=False, data=result_data, error=stderr)
        except Exception as e:
            logger.error("Error executing Python code: %s", str(e))
            return ToolResult(success=False, error=str(e))

    def _validate_code(self, code: str) -> None:
        """Validates the code to ensure it doesn't contain disallowed imports or operations."""
        logger.info("Validating Python code")
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name not in ALLOWED_IMPORTS:
                        logger.error("Disallowed import found: %s", alias.name)
                        raise ValueError(
                            f"Import '{alias.name}' not allowed. Allowed: {sorted(ALLOWED_IMPORTS)}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module not in ALLOWED_IMPORTS:
                    logger.error("Disallowed import from module: %s", module)
                    raise ValueError(
                        f"Import from '{module}' not allowed. Allowed: {sorted(ALLOWED_IMPORTS)}"
                    )
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        if node.func.value.id == "os":
                            logger.error("Disallowed use of 'os' module")
                            raise ValueError("Access to 'os' module is not allowed")
                        if node.func.value.id == "subprocess":
                            logger.error("Disallowed use of 'subprocess' module")
                            raise ValueError("Access to 'subprocess' is not allowed")
                if isinstance(node.func, ast.Name):
                    if node.func.id in ("exec", "eval", "compile", "__import__"):
                        logger.error("Disallowed function call: %s", node.func.id)
                        raise ValueError(f"'{node.func.id}()' is not allowed")
                    if node.func.id == "open":
                        logger.error("Disallowed use of 'open' function")
                        raise ValueError("File I/O is not allowed")

    def _run_code(self, code: str, timeout: int) -> tuple[str, str, int]:
        """Executes the code in a separate process with security restrictions."""
        import os
        import platform
        import resource
        import subprocess
        import tempfile

        logger.info("Running Python code in a separate process")

        # Sanitize code: prevent null bytes and other dangerous characters
        code = self._sanitize_code(code)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            tmp_path = f.name

        try:
            # Set up preexec_fn for Linux to limit resources
            preexec_fn = None
            if platform.system() == "Linux":

                def _limit_resources():
                    # Limit memory to 256MB
                    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
                    # Limit CPU time to timeout value
                    resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout))
                    # Prevent core dumps
                    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

                preexec_fn = _limit_resources

            proc = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                env={},  # Empty environment to restrict access to system variables
                preexec_fn=preexec_fn,  # Only works on Unix/Linux
            )
            if proc.returncode != 0:
                stderr = proc.stderr or f"Process exited with return code {proc.returncode}"
            else:
                stderr = proc.stderr

            return proc.stdout, stderr, proc.returncode

        except subprocess.TimeoutExpired:
            logger.error(
                "Execution timed out after %s seconds (infinite loop prevented)",
                timeout,
            )
            return (
                "",
                f"Execution timed out after {timeout}s (possible infinite loop)",
                -1,
            )
        except subprocess.CalledProcessError as e:
            logger.error("Process exited with error: %s", e.stderr)
            return_code = e.returncode if hasattr(e, "returncode") else -3
            return "", f"Process error: {e.stderr}", return_code
        except Exception as e:
            logger.error("Error executing code: %s", str(e))
            return "", str(e), -2
        finally:
            logger.info("Cleaning up temporary file: %s", tmp_path)
            try:
                os.unlink(tmp_path)
            except OSError as e:
                logger.warning("Failed to delete temporary file: %s", str(e))

    def _sanitize_code(self, code: str) -> str:
        """Sanitizes code to remove dangerous characters and null bytes."""
        logger.info("Sanitizing code input")

        # Remove null bytes
        if "\x00" in code:
            logger.warning("Null bytes detected in code, removing")
            code = code.replace("\x00", "")

        # Remove other dangerous control characters (keep only printable + newlines/tabs)
        sanitized = ""
        for char in code:
            # Keep: printable ASCII, newlines, tabs, and unicode characters
            if char.isprintable() or char in ("\n", "\t", "\r"):
                sanitized += char
            else:
                logger.debug("Removed dangerous character: %s (ord: %d)", repr(char), ord(char))

        return sanitized

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Max execution time in seconds",
                    "default": 30,
                },
            },
            "required": ["code"],
        }
