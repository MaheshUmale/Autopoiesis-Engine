import ast
import hashlib


def get_normalized_ast_hash(python_code: str) -> str:
    """Strips docstrings, comments, and variable identifiers to generate a structural AST fingerprint.

    Used for normalized AST deduplication across micro-skills.
    """
    tree = ast.parse(python_code)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            node.name = "_"
        elif isinstance(node, ast.arg):
            node.arg = "_"
        elif isinstance(node, ast.Name):
            node.id = "_"
        # Strip docstrings
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)) and node.body:
            if isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                node.body.pop(0)
    return hashlib.sha256(ast.dump(tree).encode("utf-8")).hexdigest()
