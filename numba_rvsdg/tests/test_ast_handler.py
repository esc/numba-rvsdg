from unittest import main, TestCase
import textwrap
import yaml

from numba_rvsdg.core.datastructures.ast_handler import ASTHandler


handler = ASTHandler()


class TestASTConversion(TestCase):

    def test_solo_return(self):
        def f():
            return 1
        astcfg = handler.generate_ASTCFG(f)
        expected = textwrap.dedent("""
            '0':
              instructions:
              - return 1
              jump_targets: []
              name: '0'""")
        self.assertEqual(astcfg.to_dict(), yaml.safe_load(expected))

    def test_solo_assign(self):
        def f():
            x = 1  # noqa: F841
        astcfg = handler.generate_ASTCFG(f)
        expected = textwrap.dedent("""
            '0':
              instructions:
              - x = 1
              - return
              jump_targets: []
              name: '0'""")
        self.assertEqual(astcfg.to_dict(), yaml.safe_load(expected))

    def test_assign_return(self):
        def f():
            x = 1
            return x
        astcfg = handler.generate_ASTCFG(f)
        expected = textwrap.dedent("""
            '0':
              instructions:
              - x = 1
              - return x
              jump_targets: []
              name: '0'""")
        self.assertEqual(astcfg.to_dict(), yaml.safe_load(expected))

    def test_if_return(self):
        def f(x: int):
            if x < 10:
                return 1
            return 2
        astcfg = handler.generate_ASTCFG(f)
        expected = textwrap.dedent("""
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
              instructions: []
              jump_targets:
              - '3'
              name: '2'
            '3':
              instructions:
              - return 2
              jump_targets: []
              name: '3'
              """)
        self.assertEqual(astcfg.to_dict(), yaml.safe_load(expected))

    def test_if_else_return(self):
        def f(x: int):
            if x < 10:
                return 1
            else:
                return 2
        astcfg = handler.generate_ASTCFG(f)
        expected = textwrap.dedent("""
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
            '3':
              instructions:
              - return
              jump_targets: []
              name: '3'
              """)
        self.assertEqual(astcfg.to_dict(), yaml.safe_load(expected))


if __name__ == "__main__":
    main()
