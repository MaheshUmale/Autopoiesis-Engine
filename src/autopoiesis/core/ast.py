import ast
import hashlib


class ASTNormalizer(ast.NodeTransformer):
    """Normalizes AST by stripping identifiers, function names, and docstrings for structural fingerprinting."""

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        node.name = "_"
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
            node.body = node.body[1:]
        self.generic_visit(node)
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        node.name = "_"
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
            node.body = node.body[1:]
        self.generic_visit(node)
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        node.name = "_"
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
            node.body = node.body[1:]
        self.generic_visit(node)
        return node

    def visit_arg(self, node: ast.arg) -> ast.AST:
        node.arg = "_"
        self.generic_visit(node)
        return node

    def visit_Name(self, node: ast.Name) -> ast.AST:
        node.id = "_"
        self.generic_visit(node)
        return node


def get_normalized_ast_hash(python_code: str) -> str:
    """Strips docstrings, comments, and variable identifiers to generate a structural AST fingerprint.

    Used for normalized AST deduplication across micro-skills.
    """
    tree = ast.parse(python_code)
    normalizer = ASTNormalizer()
    normalized_tree = normalizer.visit(tree)
    canonical_dump = ast.dump(normalized_tree, annotate_fields=False, include_attributes=False)
    return hashlib.sha256(canonical_dump.encode("utf-8")).hexdigest()
