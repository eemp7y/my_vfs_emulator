import unittest
import main


class TestVFSEmulator(unittest.TestCase):

    def setUp(self):
        main.VFS_DATA = {
            "type": "dir",
            "name": "/",
            "children": {
                "file1.txt": {
                    "type": "file",
                    "content": "Line 1\nLine 2\nLine 3",
                },
                "folder": {
                    "type": "dir",
                    "children": {
                        "subfile.txt": {
                            "type": "file",
                            "content": "Hello world",
                        }
                    },
                },
            },
        }
        main.CURRENT_PATH = ["/"]

    def test_cmd_ls(self):
        res = main.cmd_ls([])
        self.assertIn("file1.txt", res)
        self.assertIn("folder", res)

    def test_cmd_cd(self):
        main.cmd_cd(["folder"])
        self.assertEqual(main.CURRENT_PATH, ["/", "folder"])

    def test_cmd_tac(self):
        res = main.cmd_tac(["file1.txt"])
        expected = "Line 3\nLine 2\nLine 1"
        self.assertEqual(res, expected)

    def test_cmd_cal(self):
        res = main.cmd_cal([])
        self.assertIn("202", res)

    def test_cmd_chown(self):
        main.cmd_chown(["root:admin", "file1.txt"])
        node, _ = main.get_node_by_path("file1.txt")
        self.assertEqual(node.get("owner"), "root")
        self.assertEqual(node.get("group"), "admin")

    def test_cmd_mv(self):
        main.cmd_mv(["file1.txt", "folder/renamed.txt"])
        res = main.cmd_ls(["folder"])
        self.assertIn("renamed.txt", res)


if __name__ == "__main__":
    unittest.main()