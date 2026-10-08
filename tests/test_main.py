import unittest
from src import main


class TestVFSEmulator(unittest.TestCase):

    def setUp(self):
        main.vfs_data = {
            "type": "dir",
            "name": "/",
            "children": {
                "file1.txt": {
                    "type": "file",
                    "content": "Line 1\nLine 2\nLine 3",
                    "owner": "user",
                },
                "dir1": {
                    "type": "dir",
                    "children": {
                        "file2.txt": {"type": "file", "content": "Hello"}
                    },
                },
            },
        }
        main.current_path = ["/"]

    def test_cmd_ls(self):
        res = main.cmd_ls([])
        self.assertIn("file1.txt", res)
        self.assertIn("dir1", res)

    def test_cmd_cd(self):
        main.cmd_cd(["dir1"])
        self.assertEqual(main.current_path, ["/", "dir1"])
        res = main.cmd_ls([])
        self.assertIn("file2.txt", res)

    def test_cmd_tac(self):
        res = main.cmd_tac(["file1.txt"])
        expected = "Line 3\nLine 2\nLine 1"
        self.assertEqual(res, expected)

    def test_cmd_chown(self):
        main.cmd_chown(["admin:staff", "file1.txt"])
        node, _ = main.get_node_by_path("file1.txt")
        self.assertEqual(node["owner"], "admin")
        self.assertEqual(node["group"], "staff")

    def test_cmd_mv(self):
        main.cmd_mv(["file1.txt", "dir1/file1_moved.txt"])
        node, _ = main.get_node_by_path("dir1/file1_moved.txt")
        self.assertIsNotNone(node)


if __name__ == "__main__":
    unittest.main()