import re

from sqlalchemy import text

from app.core.database import SessionLocal
from app.core.logging import logger
from app.core.tools.base import BaseTool, ToolResult


class SQLQueryTool(BaseTool):
    @property
    def name(self) -> str:
        return "sql_query"

    @property
    def description(self) -> str:
        return (
            "Execute SQL queries against the PostgreSQL database. "
            "Use this to query stored data, analyze trends, or retrieve "
            "information from the database. Only SELECT queries are allowed."
        )

    async def execute(self, query: str, params: dict | None = None) -> ToolResult:
        try:
            logger.info("SQLQueryTool execution begins")
            self._validate_query(query)

            async with SessionLocal() as session:
                logger.info("Excecuting query")
                result = await session.execute(text(query), params or {})
                rows = result.mappings().all()
                columns = list(rows[0].keys()) if rows else []
                data = [dict(row) for row in rows]

            return ToolResult(
                success=True,
                data={
                    "columns": columns,
                    "rows": data,
                    "row_count": len(data),
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _validate_query(self, query: str) -> None:
        logger.info("Validating query")
        if not isinstance(query, str) or not query.strip():
            logger.error("Query is empty or invalid")
            raise ValueError("Query must be a non-empty SQL SELECT statement.")

        normalized = query.strip().upper()

        if not normalized.startswith("SELECT") and not normalized.startswith("WITH "):
            logger.error("Query does not start with SELECT or WITH")
            raise ValueError("Only SELECT statements and WITH CTE queries are allowed.")

        if ";" in normalized:
            logger.error("Multiple SQL statements detected")
            raise ValueError("Multiple SQL statements are not allowed.")

        if re.search(r"--|/\*|\*/|\\", normalized):
            logger.error("Comments or shell meta-commands detected")
            raise ValueError("SQL comments and shell meta-commands are not allowed.")

        forbidden_patterns = [
            r"\bINSERT\b",
            r"\bUPDATE\b",
            r"\bDELETE\b",
            r"\bCREATE\b",
            r"\bALTER\b",
            r"\bDROP\b",
            r"\bTRUNCATE\b",
            r"\bGRANT\b",
            r"\bREVOKE\b",
            r"\bCOMMIT\b",
            r"\bROLLBACK\b",
            r"\bSET\b",
            r"\bSHOW\b",
            r"\bVACUUM\b",
            r"\bANALYZE\b",
            r"\bCLUSTER\b",
            r"\bLISTEN\b",
            r"\bNOTIFY\b",
            r"\bDISCARD\b",
            r"\bCALL\b",
            r"\bEXECUTE\b",
            r"\bDO\b",
            r"\bDESCRIBE\b",
            r"\bEXPLAIN\b",
            r"\bCOPY\b",
            r"\bINTO\s+OUTFILE\b",
            r"\bPG_SLEEP\b",
            r"\bPG_TERMINATE_BACKEND\b",
            r"\bPG_CANCEL_BACKEND\b",
            r"\bDBLINK\b",
            r"\bFROM\s+PROGRAM\b",
        ]

        for pattern in forbidden_patterns:
            if re.search(pattern, normalized):
                logger.error("Forbidden SQL pattern detected: %s", pattern)
                raise ValueError("Forbidden SQL pattern detected in query.")

        if normalized.startswith("WITH ") and "SELECT" not in normalized:
            logger.error("WITH query missing SELECT")
            raise ValueError("WITH queries must include a SELECT statement.")

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "SQL SELECT query to execute",
                },
                "params": {
                    "type": "object",
                    "description": "Optional query parameters",
                    "default": None,
                },
            },
            "required": ["query"],
        }
