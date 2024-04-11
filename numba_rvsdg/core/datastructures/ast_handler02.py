import ast
import inspect
from typing import Callable
from collections import deque


from numba_rvsdg.core.datastructures.scfg import SCFG
from numba_rvsdg.core.datastructures.basic_block import PythonASTBlock


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

    def process(self) -> SCFG:
        """Create an SCFG from a Python function. """
        # convert source code into AST
        tree = ast.parse(inspect.getsource(self.code)).body
        self.codegen(tree)
        # # initialize queue
        # self.queue = deque(tree.body)
        # # check that this is a function def
        # assert isinstance(self.queue[0], ast.FunctionDef)
        # # expand the function def
        # self.handle_function_def(self.queue.popleft())
        # # insert final return None if no return at end of function
        # if not isinstance(self.queue[-1], ast.Return):
        #     self.queue.append(ast.Return(None))
        # # iterate over program
        # while self.queue:
        #     #print(self.queue, self.blocks, self.current_block, self.block_index)
        #     #breakpoint()
        #     self.handle_ast_node(self.queue.popleft())

        return SCFG(graph=self.blocks)

    def codegen(self, tree: list[ast.AST]) -> None:
        """Generate code from a list of AST nodes. """
        for node in tree:
            self.handle_ast_node(node)

    def handle_ast_node(self, node: ast.AST) -> None:
        """Handle an AST node. """
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
        #elif isinstance(node, str):
        #    if node == "ENDFOR":
        #        self.new_block()
        #    elif node.startswith("ENDTHEN") or node.startswith("ENDELSE"):
        #        index = int(node[7:])
        #        if self.current_block and isinstance(self.current_block[-1], ast.Return):
        #            self.new_terminating_block(index)
        #        else:
        #            self.new_fallthrough_block(index, self.if_stack[-1])
        #    elif node.startswith("ENDIF"):
        #        index = int(node[5:])
        #        target = self.if_stack.pop()
        #        assert index == target
        #        self.new_fallthrough_block(index, self.if_stack[-1] if
        #                                   self.if_stack else self.block_index)
        else:
            raise NotImplementedError(f"Node type {node} not implemented")

#    def new_terminating_block(self, index:int):
#        self.blocks[str(index)] = PythonASTBlock(
#            name=str(index),
#            tree=self.current_block)
#        self.current_block = []
#
#    def new_fallthrough_block(self, index:int, target:int):
#        self.blocks[str(index)] = PythonASTBlock(
#            name=str(index),
#            _jump_targets=((str(target),)),
#            tree=self.current_block)
#        self.current_block = []
#
#    def new_block(self, index: int) -> None:
#        """Create a new block. """
#        if isinstance(self.current_block[-1], ast.Return):
#            self.blocks[str(index)] = PythonASTBlock(
#                name=str(index),
#                tree=self.current_block)
#        else:
#            self.blocks[str(index)] = PythonASTBlock(
#                name=str(index),
#                _jump_targets=(str(self.if_stack[-1])),
#                tree=self.current_block)
#        self.current_block = []
#
#    def new_branch_block(self, index: int) -> tuple[int, int]:
#        """Create a new block. """
#        self.blocks[str(index)] = PythonASTBlock(
#            name=str(index),
#            _jump_targets=(str(self.block_index),
#                           str(self.block_index + 1)),
#            tree=self.current_block)
#        self.current_block = []
#        return_value = (self.block_index, self.block_index + 1)
#        self.block_index += 2
#        return return_value
#
#    def new_branch_block_empty_else(self, index:int) -> tuple[int, int]:
#        """Create a new block. """
#        self.blocks[str(index)] = PythonASTBlock(
#            name=str(index),
#            _jump_targets=(str(self.block_index),
#                           str(self.block_index + 1)),
#            tree=self.current_block)
#        self.current_block = []
#        return_value = (self.block_index, self.block_index + 1)
#        self.block_index += 1
#        return return_value

    def seal(self, index: int, instructions: list[ast.AST],
             jump_targets: tuple[int, int]=tuple()):
        if str(index) in self.blocks:
            #breakpoint()
            pass

        block = PythonASTBlock(
            name=str(index),
            _jump_targets=tuple([str(i) for i in jump_targets]),
            tree=instructions)
        self.blocks[str(index)] = block

    def open(self, index: int) -> None:
        self.current_index = index
        self.current_instructions = []

    def handle_function_def(self, node: ast.FunctionDef) -> None:
        """Handle a function definition. """
        if not isinstance(node.body[-1], ast.Return):
            node.body.append(ast.Return(None))
        self.codegen(node.body)

    def handle_assign(self, node: ast.Assign) -> None:
        """Handle an assignment. """
        self.current_instructions.append(node)

    def handle_expr(self, node: ast.Expr) -> None:
        """Handle an expression. """

    def handle_return(self, node: ast.Return) -> None:
        """Handle a return statement. """
        self.current_instructions.append(node)
        self.seal(self.block_index,
                  self.current_instructions)

    def handle_for(self, node: ast.For) -> None:
        """Handle a for loop. """
        self.new_block()
        self.current_block.append(node)
        self.queue.extend(node.body)
        self.queue.append("ENDFOR")

    def handle_if(self, node: ast.If) -> None:
        breakpoint()
        # Emit comparison value
        self.current_instructions.append(node.test)
        this_index = self.current_index
        then_index = self.block_index
        else_index = self.block_index + 1
        enif_index = self.block_index + 2
        self.block_index += 2
        self.seal(this_index, self.current_instructions,
                  (then_index, else_index))

        self.open(then_index)
        self.codegen(node.body)
        if self.current_instructions and isinstance(self.current_instructions[-1], ast.Return):
            self.seal(then_index, self.current_instructions)
        elif self.current_instructions:
            self.seal(then_index, self.current_instructions, (enif_index,))

        self.open(else_index)
        self.codegen(node.orelse)
        if self.current_instructions and isinstance(self.current_instructions[-1], ast.Return):
            self.seal(else_index, self.current_instructions)
        elif self.current_instructions:
            self.seal(else_index, self.current_instructions, (enif_index,))

        self.open(enif_index)


#    def handle_if(self, node: ast.If) -> None:
#        """Handle an if statement. """
#        self.current_block.append(node.test)
#        if (len(self.queue) >= 1
#                and isinstance(self.queue[0], str)
#                and self.queue[0].startswith("ENDIF")):
#            index = int(self.queue.popleft()[5:])
#        else:
#            index = self.block_index
#            self.block_index += 1
#        if not node.orelse:
#            t,f = self.new_branch_block_empty_else(index)
#        else:
#            t,f = self.new_branch_block(index)
#        self.queue.extend(node.body)
#        self.queue.append(f"ENDIF{t}")
#        if node.orelse:
#            self.queue.extend(node.orelse)
#            self.queue.append(f"ENDIF{f}")
#
#    def handle_if02(self, node: ast.If) -> None:
#        this_index = self.block_index
#        then_index = self.block_index + 1
#        else_index = self.block_index + 2
#        enif_index = self.block_index + 3
#        self.block_index += 4
#        self.if_stack.extend([enif_index])
#        self.queue.appendleft(f"ENDIF{enif_index}")
#        self.queue.appendleft(f"ENDELSE{else_index}")
#        self.queue.extendleft(node.orelse[::-1])
#        self.queue.appendleft(f"ENDTHEN{then_index}")
#        self.queue.extendleft(node.body[::-1])
#
#        self.current_block.append(node.test)
#        name = str(this_index)
#        self.blocks[name] = PythonASTBlock(
#            name=name,
#            _jump_targets=(str(then_index),
#                           str(else_index)),
#            tree=self.current_block)
#        self.current_block = []

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
        y = a -b
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
        y = b - a
        if y < 5:
            y = b - a
        else:
            y = 2 * b
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


h = ASTHandler(branch04)
s = h.process()
#breakpoint()
from numba_rvsdg.rendering.rendering import render_scfg
render_scfg(s)

