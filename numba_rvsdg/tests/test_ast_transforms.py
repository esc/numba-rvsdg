# mypy: ignore-errors
from unittest import main, TestCase
import textwrap
import yaml

from numba_rvsdg.core.datastructures.ast_transforms import ASTHandler


handler = ASTHandler()


class TestASTConversion(TestCase):

    def compare(self, function, expected):
        astcfg = handler.generate_ASTCFG(function)
        self.assertEqual(astcfg.to_dict(), yaml.safe_load(expected))

    def test_solo_return(self):
        def function() -> int:
            return 1

        expected = textwrap.dedent(
            """
            '0':
              instructions:
              - return 1
              jump_targets: []
              name: '0'"""
        )
        self.compare(function, expected)

    def test_solo_assign(self):
        def function() -> None:
            x = 1  # noqa: F841

        expected = textwrap.dedent(
            """
            '0':
              instructions:
              - x = 1
              - return
              jump_targets: []
              name: '0'"""
        )
        self.compare(function, expected)

    def test_assign_return(self):
        def function() -> int:
            x = 1
            return x

        expected = textwrap.dedent(
            """
            '0':
              instructions:
              - x = 1
              - return x
              jump_targets: []
              name: '0'"""
        )
        self.compare(function, expected)

    def test_if_return(self):
        def function(x: int) -> int:
            if x < 10:
                return 1
            return 2

        expected = textwrap.dedent(
            """
            '0':
              instructions:
              - x < 10
              jump_targets:
              - '1'
              - '3'
              name: '0'
            '1':
              instructions:
              - return 1
              jump_targets: []
              name: '1'
            '3':
              instructions:
              - return 2
              jump_targets: []
              name: '3'
              """
        )
        self.compare(function, expected)

    def test_if_else_return(self):
        def function(x: int) -> int:
            if x < 10:
                return 1
            else:
                return 2

        expected = textwrap.dedent(
            """
            '0':
              instructions:
              - x < 10
              jump_targets:
              - '1'
              - '2'
              name: '0'
            '1':
              instructions:
              - return 1
              jump_targets: []
              name: '1'
            '2':
              instructions:
              - return 2
              jump_targets: []
              name: '2'
              """
        )
        self.compare(function, expected)

    def test_if_else_assign(self):
        def function(x: int) -> int:
            if x < 10:
                z = 1
            else:
                z = 2
            return z

        expected = textwrap.dedent(
            """
            '0':
              instructions:
              - x < 10
              jump_targets:
              - '1'
              - '2'
              name: '0'
            '1':
              instructions:
              - z = 1
              jump_targets:
              - '3'
              name: '1'
            '2':
              instructions:
              - z = 2
              jump_targets:
              - '3'
              name: '2'
            '3':
              instructions:
              - return z
              jump_targets: []
              name: '3'
              """
        )
        self.compare(function, expected)

    def test_nested_if(self):
        def function(x: int, y: int) -> int:
            if x < 10:
                if y < 5:
                    y = 1
                else:
                    y = 2
            else:
                if y < 15:
                    y = 3
                else:
                    y = 4
            return y

        expected = textwrap.dedent(
            """
            '0':
              instructions:
              - x < 10
              jump_targets:
              - '1'
              - '2'
              name: '0'
            '1':
              instructions:
              - y < 5
              jump_targets:
              - '4'
              - '5'
              name: '1'
            '2':
              instructions:
              - y < 15
              jump_targets:
              - '7'
              - '8'
              name: '2'
            '3':
              instructions:
              - return y
              jump_targets: []
              name: '3'
            '4':
              instructions:
              - y = 1
              jump_targets:
              - '3'
              name: '4'
            '5':
              instructions:
              - y = 2
              jump_targets:
              - '3'
              name: '5'
            '7':
              instructions:
              - y = 3
              jump_targets:
              - '3'
              name: '7'
            '8':
              instructions:
              - y = 4
              jump_targets:
              - '3'
              name: '8'
              """
        )
        self.compare(function, expected)

    def test_nested_if_with_empty_else_and_return(self):
        def function(x: int, y: int) -> None:
            y << 2
            if x < 10:
                y -= 1
                if y < 5:
                    y = 1
            else:
                if y < 15:
                    y = 2
                else:
                    return
                y += 1
            return y

        expected = textwrap.dedent(
            """
            '0':
              instructions:
              - y << 2
              - x < 10
              jump_targets:
              - '1'
              - '2'
              name: '0'
            '1':
              instructions:
              - y -= 1
              - y < 5
              jump_targets:
              - '4'
              - '3'
              name: '1'
            '2':
              instructions:
              - y < 15
              jump_targets:
              - '7'
              - '8'
              name: '2'
            '3':
              instructions:
              - return y
              jump_targets: []
              name: '3'
            '4':
              instructions:
              - y = 1
              jump_targets:
              - '3'
              name: '4'
            '7':
              instructions:
              - y = 2
              jump_targets:
              - '9'
              name: '7'
            '8':
              instructions:
              - return
              jump_targets: []
              name: '8'
            '9':
              instructions:
              - y += 1
              jump_targets:
              - '3'
              name: '9'
            """
        )
        self.compare(function, expected)

    def test_elif(self):

        def function(x: int, a: int, b: int) -> int:
            if x < 10:
                return
            elif x < 15:
                y = b - a
            elif x < 20:
                y = a**2
            else:
                y = a - b
            return y

        expected = textwrap.dedent(
            """
            '0':
              instructions:
              - x < 10
              jump_targets:
              - '1'
              - '2'
              name: '0'
            '1':
              instructions:
              - return
              jump_targets: []
              name: '1'
            '2':
              instructions:
              - x < 15
              jump_targets:
              - '4'
              - '5'
              name: '2'
            '3':
              instructions:
              - return y
              jump_targets: []
              name: '3'
            '4':
              instructions:
              - y = b - a
              jump_targets:
              - '3'
              name: '4'
            '5':
              instructions:
              - x < 20
              jump_targets:
              - '7'
              - '8'
              name: '5'
            '7':
              instructions:
              - y = a ** 2
              jump_targets:
              - '3'
              name: '7'
            '8':
              instructions:
              - y = a - b
              jump_targets:
              - '3'
              name: '8'
            """
        )
        self.compare(function, expected)

    def test_simple_loop(self):
        def function() -> int:
            x = 0
            while x < 10:
                x += 1
            return x

        expected = textwrap.dedent(
            """
            '0':
              instructions:
              - x = 0
              jump_targets:
              - '1'
              name: '0'
            '1':
              instructions:
              - x < 10
              jump_targets:
              - '2'
              - '3'
              name: '1'
            '2':
              instructions:
              - x += 1
              jump_targets:
              - '1'
              name: '2'
            '3':
              instructions:
              - return x
              jump_targets: []
              name: '3'
            """
        )
        self.compare(function, expected)

    def test_nested_loop(self):
        def function() -> tuple[int, int]:
            x, y = 0, 0
            while x < 10:
                while y < 5:
                    x += 1
                    y += 1
                x += 1
            return x, y

        expected = textwrap.dedent(
            """
            '0':
              instructions:
              - x, y = (0, 0)
              jump_targets:
              - '1'
              name: '0'
            '1':
              instructions:
              - x < 10
              jump_targets:
              - '2'
              - '3'
              name: '1'
            '2':
              instructions:
              - y < 5
              jump_targets:
              - '4'
              - '5'
              name: '2'
            '3':
              instructions:
              - return (x, y)
              jump_targets: []
              name: '3'
            '4':
              instructions:
              - x += 1
              - y += 1
              jump_targets:
              - '2'
              name: '4'
            '5':
              instructions:
              - x += 1
              jump_targets:
              - '1'
              name: '5'
            """
        )
        self.compare(function, expected)

    def test_if_in_loop(self):
        def function() -> int:
            x = 0
            while x < 10:
                if x < 5:
                    x += 2
                else:
                    x += 1
            return x

        expected = textwrap.dedent(
            """
            '0':
              instructions:
              - x = 0
              jump_targets:
              - '1'
              name: '0'
            '1':
              instructions:
              - x < 10
              jump_targets:
              - '2'
              - '3'
              name: '1'
            '2':
              instructions:
              - x < 5
              jump_targets:
              - '4'
              - '5'
              name: '2'
            '3':
              instructions:
              - return x
              jump_targets: []
              name: '3'
            '4':
              instructions:
              - x += 2
              jump_targets:
              - '1'
              name: '4'
            '5':
              instructions:
              - x += 1
              jump_targets:
              - '1'
              name: '5'
            """
        )
        self.compare(function, expected)

    def test_loop_in_if(self):
        def function(a: bool) -> int:
            x = 0
            if a is True:
                while x < 10:
                    x += 2
            else:
                while x < 10:
                    x += 1
            return x

        expected = textwrap.dedent(
            """
            '0':
              instructions:
              - x = 0
              - a is True
              jump_targets:
              - '1'
              - '2'
              name: '0'
            '1':
              instructions:
              - x < 10
              jump_targets:
              - '4'
              - '3'
              name: '1'
            '2':
              instructions:
              - x < 10
              jump_targets:
              - '6'
              - '3'
              name: '2'
            '3':
              instructions:
              - return x
              jump_targets: []
              name: '3'
            '4':
              instructions:
              - x += 2
              jump_targets:
              - '1'
              name: '4'
            '6':
              instructions:
              - x += 1
              jump_targets:
              - '2'
              name: '6'
            """
        )
        self.compare(function, expected)

    def test_loop_break_continue(self):
        def function() -> int:
            x = 0
            while x < 10:
                x += 1
                if x % 2 == 0:
                    continue
                elif x == 9:
                    break
                else:
                    x += 1
            return x

        expected = textwrap.dedent(
            """
            '0':
              instructions:
              - x = 0
              jump_targets:
              - '1'
              name: '0'
            '1':
              instructions:
              - x < 10
              jump_targets:
              - '2'
              - '3'
              name: '1'
            '2':
              instructions:
              - x += 1
              - x % 2 == 0
              jump_targets:
              - '4'
              - '5'
              name: '2'
            '3':
              instructions:
              - return x
              jump_targets: []
              name: '3'
            '4':
              instructions:
              - continue
              jump_targets:
              - '1'
              name: '4'
            '5':
              instructions:
              - x == 9
              jump_targets:
              - '7'
              - '8'
              name: '5'
            '7':
              instructions:
              - break
              jump_targets:
              - '3'
              name: '7'
            '8':
              instructions:
              - x += 1
              jump_targets:
              - '1'
              name: '8'
            """
        )
        self.compare(function, expected)


if __name__ == "__main__":
    main()
