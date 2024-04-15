import ast
import inspect
from typing import Callable
import textwrap


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

    def set_jump_targets(self, *indices: int) -> None:
        self.jump_targets = [str(a) for a in indices]

    def is_return(self) -> bool:
        return (self.instructions and
                isinstance(self.instructions[-1], ast.Return))

    def is_break(self) -> bool:
        return (self.instructions and
                isinstance(self.instructions[-1], ast.Break))

    def is_continue(self) -> bool:
        return (self.instructions and
                isinstance(self.instructions[-1], ast.Continue))

    def seal(self, head_index, exit_index, dflt_index):
        if self.is_continue():
            self.set_jump_targets(head_index)
        elif self.is_break():
            self.set_jump_targets(exit_index)
        elif self.is_return():
            pass
        else:
            self.set_jump_targets(dflt_index)

    def __repr__(self) -> str:
        return f"WriteableBasicBlock({self.name}, {self.instructions}, {self.jump_targets})"


class ASTCFG(dict):
    """ A CFG consisting of WriteableBasicBlocks. """

    def convert_blocks(self) -> dict[str, PythonASTBlock]:
        """ Convert WriteableBasicBlocks to PythonASTBlocks.  """
        return {v.name:
                PythonASTBlock(
                    v.name,
                    tree=v.instructions,
                    _jump_targets=tuple(v.jump_targets))
                for v in self.values()}

    def to_dict(self) -> dict[str, dict[str, object]]:
        """ Convert ASTCFG to simple dict based datastructure. """
        return {k: {"name": v.name,
                    "instructions": [ast.unparse(n) for n in v.instructions],
                    "jump_targets": v.jump_targets,
                    } for (k, v) in self.items()}

    def to_yaml(self) -> str:
        """ Convert ASTCFG to yaml based string serialization. """
        import yaml
        return yaml.dump(self.to_dict())

    def to_SCFG(self):
        """ Convert ASTCFG to SCFG"""
        return SCFG(graph=self.convert_blocks())


class ASTHandler:
    """ASTHandler class.

    The ASTHandler class is responsible for converting code in the form of a
    Python Abstract Syntax Tree (ast) into CFG/SCFG.

    """

    def __init__(self) -> None:
        # Monotonically increasing block index
        self.block_index: int = None
        # Dict mapping block indices as strings to WriteableBasicBlocks
        # (This is the datastructure to hold the CFG.)
        self.blocks: ASTCFG = None
        # Current block being written to
        self.current_block: WriteableBasicBlock = None
        # Stacks for header and exiting block of current loop
        self.loop_head_stack: list[int] = None
        self.loop_exit_stack: list[int] = None

    def reset(self):
        """ Reset the handler to initial state. """
        # Block index starts at 1, 0 is reserved for the genesis block
        self.block_index = 1
        # Initialize blocks dict (CFG)
        self.blocks = ASTCFG()
        # Initialize first (genesis) block, assume it's named zero
        # (This also initializes the self.current_block attribute.)
        self.add_block("0")
        # Initialize loop stacks
        self.loop_head_stack, self.loop_exit_stack = [], []

    def handle(self, code: Callable) -> None:
        """Handle Python function. """
        self.reset()
        # Convert source code into AST
        tree = ast.parse(textwrap.dedent(inspect.getsource(code))).body
        # Assert that the code handed in was a function, we can only convert
        # functions.
        assert isinstance(tree[0], ast.FunctionDef)
        # Run recrisive code generation
        self.codegen(tree)

    def generate_ASTCFG(self, code: Callable) -> ASTCFG:
        """ Generate ASTCFG from Python function. """
        self.handle(code)
        return self.blocks

    def generate_SCFG(self, code: Callable) -> SCFG:
        """ Generate SCFG from Python function. """
        self.handle(code)
        return self.blocks.to_SCFG()

    def codegen(self, tree: list[ast.AST]) -> None:
        """Recursively Generate code from a list of AST nodes. """
        for node in tree:
            self.handle_ast_node(node)

    def add_block(self, index: int) -> None:
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
                               ast.Return,
                               ast.Break,
                               ast.Continue,
                               )):
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

    def seal(self, default_index) -> None:
        """ Seal the current block by setting the jump_targets. """
        self.current_block.seal(
            self.loop_head_stack[-1] if self.loop_head_stack else -1,
            self.loop_exit_stack[-1] if self.loop_exit_stack else -1,
            default_index)

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
        self.current_block.set_jump_targets(then_index, else_index)

        # Create a new block for the then branch
        self.add_block(then_index)
        # Recursively process then branch
        self.codegen(node.body)
        # After recursion, current_block may need a jump target
        self.seal(enif_index)

        # Create a new block for the else branch
        self.add_block(else_index)
        # Recursively process else branch
        self.codegen(node.orelse)
        # After recursion, current_block may need a jump target
        self.seal(enif_index)

        # Create a new block for the end-if statements, if any
        self.add_block(enif_index)

    def handle_while(self, node):
        """ Handle while statement. """
        # Preallocate header, body and exiting indices
        head_index = self.block_index
        body_index = self.block_index + 1
        exit_index = self.block_index + 2
        self.block_index += 3

        # Point whatever the current block to header block
        self.current_block.set_jump_targets(head_index)

        # Create header block
        self.add_block(head_index)
        # Emit comparison expression into it
        self.current_block.instructions.append(node.test)
        # Set the jump targets to be the body and the exiting latch
        self.current_block.set_jump_targets(body_index, exit_index)

        # Create body block
        self.add_block(body_index)

        # setup loop stacks for recursion
        self.loop_head_stack.append(head_index)
        self.loop_exit_stack.append(exit_index)

        # Recurse into it
        self.codegen(node.body)

        # pop values from loop stack post recursion
        self.loop_head_stack.pop()
        self.loop_exit_stack.pop()

        # After recursion, seal current block
        self.seal(head_index)

        # Create exit block
        self.add_block(exit_index)

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
        render_scfg(self.blocks.to_SCFG())


def loop_break():
    x = 0
    while x < 10:
        if x < 3:
            break
        else:
            x += 1
    return x


def loop_continue():
    x = 0
    while x < 10:
        if x > 5:
            continue
        x += 1
    return x


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

if __name__ == "__main__":
    h = ASTHandler()
    s = h.generate_SCFG(loop_continue)
    render_scfg(s)
