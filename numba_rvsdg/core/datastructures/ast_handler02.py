import ast
import inspect
from typing import Callable
from collections import deque


from numba_rvsdg.core.datastructures.scfg import SCFG
from numba_rvsdg.core.datastructures.basic_block import PythonASTBlock
from numba_rvsdg.rendering.rendering import render_scfg

class WriteableBasicBlock:
    """ A basic block that can be written to.

    The ast -> cfg algorithm requires a basic block that can be written to.

    """
    def __init__(self, name: str,
                 instructions: list[ast.AST]=None,
                 jump_targets: tuple[str, str]=None) -> None:
        self.name = name
        self.instructions = [] if instructions is None else instructions
        self.jump_targets = () if jump_targets is None else jump_targets


def convert(blocks: dict[str, WriteableBasicBlock]) -> dict[str, PythonASTBlock]:
    """ Convert CFG of WriteableBasicBlocks to CFG of PythonASTBlocks.  """
    new_blocks = {}
    for v in blocks.values():
        new_blocks[v.name] = PythonASTBlock(
            v.name, tree=v.instructions, _jump_targets=v.jump_targets)
    return new_blocks


class ASTHandler:
    """ASTHandler class.

    The ASTHandler class is responsible for converting code in the form of a
    Python Abstract Syntax Tree (ast) into CFG/SCFG.

    """

    def __init__(self, code: Callable) -> None:
        self.code = code
        self.block_index = 1
        self.blocks = {}
        self.current_index = 0
        self.current_instructions = []
        self.if_stack = []
        self.current_block = WriteableBasicBlock(name=str(self.current_index))
        self.blocks[str(self.current_index)] = self.current_block

    def process(self) -> SCFG:
        """Create an SCFG from a Python function. """
        # convert source code into AST
        tree = ast.parse(inspect.getsource(self.code)).body
        # run recrisive code generation
        self.codegen(tree)
        # add last block to CFG
        self.blocks[self.current_block.name] = self.current_block
        # create SCFG using PythonASTBlocks
        return SCFG(graph=convert(self.blocks))

    def codegen(self, tree: list[ast.AST]) -> None:
        """Recursively Generate code from a list of AST nodes. """
        for node in tree:
            self.handle_ast_node(node)

    def handle_ast_node(self, node: ast.AST) -> None:
        """Dispatch an AST node to handler. """
        if isinstance(node, ast.FunctionDef):
            self.handle_function_def(node)
        elif isinstance(node, ast.Assign):
            self.handle_assign(node)
        elif isinstance(node, ast.Expr):
            self.handle_expr(node)
        elif isinstance(node, ast.Return):
            self.handle_return(node)
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
        if not isinstance(node.body[-1], ast.Return):
            node.body.append(ast.Return(None))
        self.codegen(node.body)

    def handle_assign(self, node: ast.Assign) -> None:
        """Handle an assignment. """
        self.current_block.instructions.append(node)

    def handle_return(self, node: ast.Return) -> None:
        """Handle a return statement. """
        self.current_block.instructions.append(node)
        self.current_block.jump_targets = ()

    def handle_if(self, node: ast.If) -> None:
        """ Handle if statement. """

        # Emit comparison value to current block
        self.current_block.instructions.append(node.test)

        # Preallocate block indices for then, else, and end-if
        then_index = self.block_index
        else_index = self.block_index + 1
        enif_index = self.block_index + 2
        self.block_index += 3

        # Setup jump targets for current block
        self.current_block.jump_targets = (str(then_index), str(else_index))
        # Add block to CFG
        self.blocks[self.current_block.name] = self.current_block

        # Add end-if index to if stack. This must be done before any recursive
        # calls, such that the end-if blocks in nested if statements know where
        # to point to.
        self.if_stack.append(enif_index)

        # Create a new block for the then branch
        self.current_block = WriteableBasicBlock(name=str(then_index))
        self.current_block.jump_targets = (str(enif_index),)
        self.blocks[str(then_index)] = self.current_block
        self.codegen(node.body)

        # Create a new block for the else branch
        self.current_block = WriteableBasicBlock(name=str(else_index))
        self.current_block.jump_targets = (str(enif_index),)
        self.blocks[str(else_index)] = self.current_block
        self.codegen(node.orelse)

        # All recursive calls have been made, so we can now pop the end-if.
        self.if_stack.pop()
        # Create a new block for the end-if
        self.current_block = WriteableBasicBlock(name=str(enif_index))
        self.blocks[self.current_block.name] = self.current_block
        # If there are any elements on the if stack, we need to update the jump
        # targets of the current end-if block.
        if self.if_stack:
            self.current_block.jump_targets = str(self.if_stack[-1])

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

def branch01(a: int, b:int) -> None:
    if x < 10:
        return 1
    return 2

def branch02(a: int, b:int) -> None:
    if x < 10:
        y = a + b
    z = a - b

def branch03(a: int, b:int) -> None:
    if x < 10:
        return
    else:
        y = b -c
    return y

def branch04(x:int, y:int, a: int, b:int) -> None:
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
    return y

def branch05(x:int, y:int, a: int, b:int) -> None:
    if x < 10:
        if y < 5:
            y = a - b
    else:
        if y < 15:
            y = b - a
        else:
            return
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
#breakpoint()
render_scfg(s)

