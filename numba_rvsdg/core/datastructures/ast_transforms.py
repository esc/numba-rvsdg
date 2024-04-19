import ast
import inspect
from typing import Callable
import textwrap
from dataclasses import dataclass

from typing import Any, MutableMapping

from numba_rvsdg.core.datastructures.scfg import SCFG
from numba_rvsdg.core.datastructures.basic_block import PythonASTBlock
from numba_rvsdg.rendering.rendering import render_scfg


class WritableASTBlock:
    """A basic block containing Python AST that can be written to.

    The ast -> cfg algorithm requires a basic block that can be written to.

    """

    def __init__(
        self,
        name: str,
        instructions: list[ast.AST] | None = None,
        jump_targets: list[str] | None = None,
    ) -> None:
        self.name = name
        self.instructions: list[ast.AST] = (
            [] if instructions is None else instructions
        )
        self.jump_targets: list[str] = (
            [] if jump_targets is None else jump_targets
        )

    def set_jump_targets(self, *indices: int) -> None:
        """Set jump targets for the block."""
        self.jump_targets = [str(a) for a in indices]

    def is_instruction(self, instruction: type[ast.AST]) -> bool:
        """Check if the last instruction is of a certain type."""
        return len(self.instructions) > 0 and isinstance(
            self.instructions[-1], instruction
        )

    def is_return(self) -> bool:
        """Check if the last instruction is a return statement."""
        return self.is_instruction(ast.Return)

    def is_break(self) -> bool:
        """Check if the last instruction is a break statement."""
        return self.is_instruction(ast.Break)

    def is_continue(self) -> bool:
        """Check if the last instruction is a continue statement."""
        return self.is_instruction(ast.Continue)

    def seal_outside_loop(self, index: int) -> None:
        """Seal the block by setting the jump targets based on the last
        instruction.
        """
        if self.is_return():
            pass
        else:
            self.set_jump_targets(index)

    def seal_inside_loop(
        self, head_index: int, exit_index: int, default_index: int
    ) -> None:
        """Seal the block by setting the jump targets based on the last
        instruction and taking into account that this block is nested in a
        loop.
        """
        if self.is_continue():
            self.set_jump_targets(head_index)
        elif self.is_break():
            self.set_jump_targets(exit_index)
        elif self.is_return():
            pass
        else:
            self.set_jump_targets(default_index)

    def __repr__(self) -> str:
        return (
            f"WritableASTBlock({self.name}, "
            "{self.instructions}, {self.jump_targets})"
        )


class ASTCFG(dict[str, WritableASTBlock]):
    """A CFG consisting of WritableASTBlocks."""

    def convert_blocks(self) -> MutableMapping[str, Any]:
        """Convert WritableASTBlocks to PythonASTBlocks."""
        return {
            v.name: PythonASTBlock(
                v.name,
                tree=v.instructions,
                _jump_targets=tuple(v.jump_targets),
            )
            for v in self.values()
        }

    def to_dict(self) -> dict[str, dict[str, object]]:
        """Convert ASTCFG to simple dict based datastructure."""
        return {
            k: {
                "name": v.name,
                "instructions": [ast.unparse(n) for n in v.instructions],
                "jump_targets": v.jump_targets,
            }
            for (k, v) in self.items()
        }

    def to_yaml(self) -> str:
        """Convert ASTCFG to yaml based string serialization."""
        import yaml

        return yaml.dump(self.to_dict())

    def to_SCFG(self) -> SCFG:
        """Convert ASTCFG to SCFG"""
        return SCFG(graph=self.convert_blocks())

    def prune_unreachable(self) -> set[WritableASTBlock]:
        """Prune unreachable nodes from the CFG."""
        # Assume that the entry block is named zero (0)
        to_visit, reachable, unreachable = set("0"), set(), set()
        # Visit all reachable blocks
        while to_visit:
            block = to_visit.pop()
            if block not in reachable:
                # Add block to reachable set
                reachable.add(block)
                # Update to_visit with jump targets of the block
                to_visit.update(self[block].jump_targets)
        # Remove unreachable blocks
        for block in list(self.keys()):
            if block not in reachable:
                unreachable.add(self.pop(block))
        return unreachable

    def prune_empty(self) -> set[WritableASTBlock]:
        """Prune empty nodes from the CFG."""
        empty = set()
        for name, block in list(self.items()):
            if not block.instructions:
                empty.add(self.pop(name))
                # Empty nodes can only have a single jump target.
                it = block.jump_targets[0]
                # iterate over the nodes looking for nodes that point to the
                # removed node
                for b in list(self.values()):
                    if len(b.jump_targets) == 0:
                        continue
                    elif len(b.jump_targets) == 1:
                        if b.jump_targets[0] == name:
                            b.jump_targets[0] = it
                    elif len(b.jump_targets) == 2:
                        if b.jump_targets[0] == name:
                            b.jump_targets[0] = it
                        elif b.jump_targets[1] == name:
                            b.jump_targets[1] = it
        return empty


@dataclass(frozen=True)
class LoopIndices:
    """Structure to hold the head and exit block indices of a loop."""
    head: int
    exit: int


class AST2SCFGTransformer:
    """AST2SCFGTransformer

    The AST2SCFGTransformer class is responsible for transforming code in the
    form of a Python Abstract Syntax Tree (ast) into CFG/SCFG.

    """

    def __init__(self, code: Callable[..., Any], prune: bool = True) -> None:
        # Prune empty and unreachable nodes from the CFG
        self.prune: bool = prune
        # Save the code for transformation
        self.code: Callable[..., Any] = code
        # Monotonically increasing block index, 0 is reserved for genesis
        self.block_index: int = 1
        # Dict mapping block indices as strings to WritableASTBlocks
        # (This is the datastructure to hold the CFG.)
        self.blocks: ASTCFG = ASTCFG()
        # Initialize first (genesis) block, assume it's named zero
        # (This also initializes the self.current_block attribute.)
        self.add_block(0)
        # Stack for header and exiting block of current loop
        self.loop_stack: list[LoopIndices] = []

    def transform_to_ASTCFG(self) -> ASTCFG:
        """Generate ASTCFG from Python function."""
        self.transform()
        return self.blocks

    def transform_to_SCFG(self) -> SCFG:
        """Generate SCFG from Python function."""
        self.transform()
        return self.blocks.to_SCFG()

    def add_block(self, index: int) -> None:
        """Create block, add to CFG and set as current_block."""
        self.blocks[str(index)] = self.current_block = WritableASTBlock(
            name=str(index)
        )

    def seal(self, default_index: int) -> None:
        """Seal the current block by setting the jump_targets."""
        if self.loop_stack:
            self.current_block.seal_inside_loop(
                self.loop_stack[-1].head,
                self.loop_stack[-1].exit,
                default_index,
            )
        else:
            self.current_block.seal_outside_loop(default_index)

    def transform(self) -> None:
        """Transform Python function stored as self.code."""
        # Convert source code into AST
        tree = ast.parse(textwrap.dedent(inspect.getsource(self.code))).body
        # Assert that the code handed in was a function, we can only convert
        # functions.
        assert isinstance(tree[0], ast.FunctionDef)
        # Run recrisive code generation
        self.codegen(tree)
        # Prune if needed
        if self.prune:
            _ = self.blocks.prune_unreachable()
            _ = self.blocks.prune_empty()

    def codegen(self, tree: list[type[ast.AST]] | list[ast.stmt]) -> None:
        """Recursively Generate code from a list of AST nodes."""
        for node in tree:
            self.handle_ast_node(node)

    def handle_ast_node(self, node: type[ast.AST] | ast.stmt) -> None:
        """Dispatch an AST node to handle."""
        if isinstance(node, ast.FunctionDef):
            self.handle_function_def(node)
        elif isinstance(
            node,
            (
                ast.Assign,
                ast.AugAssign,
                ast.Expr,
                ast.Return,
                ast.Break,
                ast.Continue,
            ),
        ):
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
        """Handle a function definition."""
        # Insert implicit return None, if the function isn't terminated
        if not isinstance(node.body[-1], ast.Return):
            node.body.append(ast.Return(None))
        self.codegen(node.body)

    def handle_if(self, node: ast.If) -> None:
        """Handle if statement."""
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

    def handle_while(self, node: ast.While) -> None:
        """Handle while statement."""
        # If the current block already has instructions, we need a new block as
        # header. Otherwise just re-use the current-block.
        if self.current_block.instructions:
            # Preallocate header, body and exiting indices
            head_index = self.block_index
            body_index = self.block_index + 1
            exit_index = self.block_index + 2
            self.block_index += 3

            # Point whatever the current block to header block
            self.current_block.set_jump_targets(head_index)
            # And create new header block
            self.add_block(head_index)
        else:
            # body and exiting indices
            head_index = int(self.current_block.name)
            body_index = self.block_index
            exit_index = self.block_index + 1
            self.block_index += 2

        # Emit comparison expression into header
        self.current_block.instructions.append(node.test)
        # Set the jump targets to be the body and the exiting latch
        self.current_block.set_jump_targets(body_index, exit_index)

        # Create body block
        self.add_block(body_index)

        # setup loop stack for recursion
        self.loop_stack.append(LoopIndices(head_index, exit_index))

        # Recurse into it
        self.codegen(node.body)
        # After recursion, seal current block
        self.seal(head_index)

        # pop values from loop stack post recursion
        loop_indices = self.loop_stack.pop()
        assert (
            loop_indices.head == head_index and loop_indices.exit == exit_index
        )

        # Create exit block
        self.add_block(exit_index)

    def handle_for(self, node: ast.For) -> None:
        # Preallocate indices for blocks
        head_index = self.block_index
        body_index = self.block_index + 1
        else_index = self.block_index + 2
        exit_index = self.block_index + 3
        self.block_index += 4

        # Assign the components of the for-loop to variables
        target = ast.unparse(node.target)
        iter_setup = ast.unparse(node.iter)
        iter_assign = "__iterator__"
        last_target_value = "__iter_last__"

        # Emit iter setup to pre-header
        preheader_code = textwrap.dedent(
            f"""
            {iter_assign} = iter({iter_setup})
            {target} = None
        """
        )
        self.codegen(ast.parse(preheader_code).body)

        # Point whatever the current block to header block
        self.current_block.set_jump_targets(head_index)
        # And create new header block
        self.add_block(head_index)

        # Emit header instructions
        header_code = textwrap.dedent(
            f"""
            {last_target_value} = {target}
            {target} = next({iter_assign}, "__sentinel__")
            {target} != "__sentinel__"
        """
        )
        self.codegen(ast.parse(header_code).body)
        # Set the jump targets to be the body and the exiting latch
        self.current_block.set_jump_targets(body_index, else_index)

        # Create body block
        self.add_block(body_index)

        # setup loop stack for recursion
        self.loop_stack.append(LoopIndices(head_index, exit_index))

        # Recurse into it
        self.codegen(node.body)
        # After recursion, seal current block
        self.seal(head_index)

        # pop values from loop stack post recursion
        loop_indices = self.loop_stack.pop()
        assert (
            loop_indices.head == head_index and loop_indices.exit == exit_index
        )

        # Create else block
        self.add_block(else_index)
        self.current_block.set_jump_targets(exit_index)

        # Emit orelse instructions. Needs to be prefixed with an assignment
        # such that the for loop target can escape the scope of the loop.
        else_code = textwrap.dedent(
            f"""
            {target} = {last_target_value}
        """
        )
        self.codegen(ast.parse(else_code).body)
        self.codegen(node.orelse)

        # Create exit block
        self.add_block(exit_index)

    def render(self) -> None:
        """Render the CFG contained in this transformer as a SCFG.

        Useful for debugging purposes, set a breakpoint and then render to view
        intermediary results.

        """
        render_scfg(self.blocks.to_SCFG())


def AST2SCFG(code: Callable[..., Any]) -> SCFG:
    return AST2SCFGTransformer(code).transform_to_SCFG()


def SCFG2AST(scfg: SCFG) -> ast.FunctionDef:  # type: ignore
    # TODO
    pass


if __name__ == "__main__":

    def function(a: int, b: int) -> int:
        for i in range(100):
            i += 1
            if i == a:
                i = 666
                return i
            elif i == b:
                i = 777
                return i
            else:
                continue
        return i

    s = AST2SCFG(function)
    render_scfg(s)
