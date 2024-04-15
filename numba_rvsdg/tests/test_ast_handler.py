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
            x = 1
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


if __name__ == "__main__":
    main()
