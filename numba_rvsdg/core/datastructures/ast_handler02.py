import ast
import inspect
from typing import Callable


from numba_rvsdg.core.datastructures.scfg import SCFG
from numba_rvsdg.core.datastructures.basic_block import PythonASTBlock
from numba_rvsdg.rendering.rendering import render_scfg


class WriteableBasicBlock:
    """ A basic block that can be written to.

    The ast -> cfg algorithm requires a basic block that can be written to.

    """
    def __init__(self, name: str,
                 instructions: list[ast.AST] = None,
                 jump_targets: list[str, str] = None) -> None:
        self.name = name
        self.instructions = [] if instructions is None else instructions
        self.jump_targets = [] if jump_targets is None else jump_targets

    def is_terminator(self):
        return (self.instructions and
                isinstance(self.instructions[-1], ast.Return))

    def __repr__(self):
        return f"WriteableBasicBlock({self.name}, {self.instructions}, {self.jump_targets})"


def convert(blocks: dict[str, WriteableBasicBlock]
            ) -> dict[str, PythonASTBlock]:
    """ Convert CFG of WriteableBasicBlocks to CFG of PythonASTBlocks.  """
    return {v.name: PythonASTBlock(
        v.name,
        tree=v.instructions,
        _jump_targets=tuple(v.jump_targets))
        for v in blocks.values()}


class ASTHandler:
    """ASTHandler class.

    The ASTHandler class is responsible for converting code in the form of a
    Python Abstract Syntax Tree (ast) into CFG/SCFG.

    """

    def __init__(self, code: Callable) -> None:
        # Source code to convert
        self.code = code
        # Monotonically increasing block index
        self.block_index = 1
        # Dict mapping block indices as strings to WriteableBasicBlocks
        # (This is the datastructure to hold the CFG.)
        self.blocks = {}
        # Initialize first (genesis) block, assume it's named zero and addit to
        # the CFG
        self.blocks["0"] = self.current_block = WriteableBasicBlock(name="0")

    def process(self) -> SCFG:
        """Create an SCFG from a Python function. """
        # Convert source code into AST
        tree = ast.parse(inspect.getsource(self.code)).body
        # Assert that the code handed in was a function, we can only convert
        # functions.
        assert isinstance(tree[0], ast.FunctionDef)
        # Run recrisive code generation
        self.codegen(tree)
        # Create SCFG using PythonASTBlocks and return
        return SCFG(graph=convert(self.blocks))

    def codegen(self, tree: list[ast.AST]) -> None:
        """Recursively Generate code from a list of AST nodes. """
        for node in tree:
            self.handle_ast_node(node)

    def add_block(self, index: int):
        """ Create block, add to CFG and set as current_block. """
        self.blocks[str(index)] = self.current_block = \
            WriteableBasicBlock(name=str(index))

    def handle_ast_node(self, node: ast.AST) -> None:
        """Dispatch an AST node to handler. """
        if isinstance(node, ast.FunctionDef):
            self.handle_function_def(node)
        elif isinstance(node, (ast.Assign,
                               ast.AugAssign,
                               ast.Expr,
                               ast.Return)):
            self.current_block.instructions.append(node)
        elif isinstance(node, ast.If):
            self.handle_if(node)
        elif isinstance(node, ast.While):
            self.handle_while(node)
        elif isinstance(node, ast.For):
            self.handle_for(node)
        else:
            raise NotImplementedError(f"Node type {node} not implemented")

    def handle_function_def(self, node: ast.FunctionDef) -> None:
        """Handle a function definition. """
        # Insert implicit return None, if the function isn't terminated
        if not isinstance(node.body[-1], ast.Return):
            node.body.append(ast.Return(None))
        self.codegen(node.body)

    def handle_if(self, node: ast.If) -> None:
        """ Handle if statement. """
        # Preallocate block indices for then, else, and end-if
        then_index = self.block_index
        else_index = self.block_index + 1
        enif_index = self.block_index + 2
        self.block_index += 3

        # Emit comparison value to current block
        self.current_block.instructions.append(node.test)
        # Setup jump targets for current block
        self.current_block.jump_targets = [str(then_index), str(else_index)]

        # Create a new block for the then branch
        self.add_block(then_index)
        # Recursively process then branch
        self.codegen(node.body)
        # After recursion, current_block may need a jump target
        if not self.current_block.is_terminator():
            self.current_block.jump_targets = [str(enif_index)]

        # Create a new block for the else branch
        self.add_block(else_index)
        # Recursively process else branch
        self.codegen(node.orelse)
        # After recursion, current_block may need a jump target
        if not self.current_block.is_terminator():
            self.current_block.jump_targets = [str(enif_index)]

        # Create a new block for the end-if statements, if any
        self.add_block(enif_index)

    def handle_while(self, node):
        pass

    def prune_empty(self):
        for i in list(self.blocks.values()):
            if not i.instructions:
                self.blocks.pop(i.name)
                # Empty nodes can only have a single jump target.
                it = i.jump_targets[0]
                # iterate over the nodes looking for nodes that point to the
                # removed node
                for j in list(self.blocks.values()):
                    if len(j.jump_targets) == 0:
                        continue
                    elif len(j.jump_targets) == 1:
                        if j.jump_targets[0] == i.name:
                            j.jump_targets[0] = it
                    elif len(j.jump_targets) == 2:
                        if j.jump_targets[0] == i.name:
                            j.jump_targets[0] = it
                        elif j.jump_targets[1] == i.name:
                            j.jump_targets[1] = it

    def render(self):
        """ Render the CFG contained in this handler as a SCFG.

        Useful for debugging purposes, set a breakpoint and then render to view
        intermediary results.

        """
        s = SCFG(graph=convert(self.blocks))
        render_scfg(s)


def solo_return():
    return 1


def solo_assign():
    x = 1


def assign_return():
    x = 1
    return x


def acc():
    r = 0
    for i in range(10):
        r = r + 1
    return r


def branch01(x: int) -> None:
    if x < 10:
        return 1
    return 2


def branch02(x: int, y: int, a: int, b: int) -> None:
    if x < 10:
        y = a + b
    z = a - b


def branch03(x: int, a: int, b: int) -> None:
    if x < 10:
        return
    else:
        y = b - a
    return y


def branch04(x: int, y: int, a: int, b: int) -> None:
    if x < 10:
        if y < 5:
            y = a - b
        else:
            y = 2 * a
    else:
        if y < 15:
            y = b - a
        else:
            y = b ** 2
    return y, z


def branch05(x: int, y: int, a: int, b: int) -> None:
    y *= 2
    if x < 10:
        y -= 1
        if y < 5:
            y = a - b
    else:
        if y < 15:
            y = b - a
        else:
            return
        y += 1
    return y


#def branch02(a: int, b:int) -> None:
#    if x < 10:
#        return 1
#    else:
#        return 2
#
#def branch03(a: int, b:int) -> None:
#    x = a + b
#    if x < 10:
#        return 1
#    else:
#        if x < 5:
#            return 2
#        else:
#            return 3
#
#def branch04(a: int, b:int) -> None:
#    x = a + b
#    if x < 10:
#        if x < 2:
#            return 1
#        else:
#            return 2
#    else:
#        if x < 5:
#            return 3
#        else:
#            return 4
#
#def branch05(a: int, b:int) -> None:
#    if x < 10:
#        return 1
#    y = b + 2
#    if y < 5:
#        return 2
#    return 0


h = ASTHandler(branch05)
s = h.process()
render_scfg(s)
