#!/usr/bin/python3
import unittest
import os
import logging
from pathlib import Path

import yaml
from ctgrzr.src.cli import cli, get_arg_parser
from ctgrzr.src.ctgrzr_config import load_config
from ctgrzr.src.env import get_config_path_as_string, resolve_config_path
from ctgrzr.src.logger import get_logger, set_logging_level
from ctgrzr.src.operation import run_command
from ctgrzr.src.symlinks import search_symlinks_in_directory

set_logging_level(logging.DEBUG)
# NOTE change back to CRITICAL


class CtgrzrTest(unittest.TestCase):

    arg_parser = get_arg_parser()
    root_path = Path('/ctgrzr-test')
    file1 = root_path / 'file1'
    file2 = root_path / 'file2'
    file3 = root_path / 'file3'
    not_exists = root_path / 'not-exist'
    file1_symlink = root_path / 'file1-symlink'
    category1 = 'category1'
    category2 = 'category2'
    config_path = resolve_config_path(get_config_path_as_string(None))
    template_config_path = config_path.parent / 'template-config.yaml'
    side_effect_file = Path('/side-effect')
    operation_file = config_path.parent / 'operation.yaml'

    def setUp(self):
        self.root_path.mkdir(parents=True)
        run_command(f'echo a > {self.file1}')
        run_command(f'echo b > {self.file2}')
        run_command(f'echo c > {self.file3}')
        self.file1_symlink.symlink_to(self.file1)
        if not self.operation_file.parent.exists():
            self.operation_file.parent.mkdir(parents=True)
        with open(self.operation_file, 'w') as f:
            f.write(yaml.dump({
                self.category1: 'echo "Category1 - {}" >> ' + f'"{self.side_effect_file}"',
                self.category2: 'echo "Category2 - {}" >> ' + f'"{self.side_effect_file}"'
            }))

    def tearDown(self):
        run_command(f'rm -rf {self.root_path}', check=True)
        if self.config_path.exists():
            run_command(f'rm "{self.config_path}"')
        if self.template_config_path.exists():
            run_command(f'rm "{self.template_config_path}"')
        if self.side_effect_file.exists():
            run_command(f'rm "{self.side_effect_file}"')
        # if self.operation_file.exists():
        #     run_command(f'rm "{self.operation_file}"')

    # TODO if necessary extract to separate test class
    # Because Initialization could be reused in other test cases
    def test_add_remove(self):
        args_add_path1 = self.arg_parser.parse_args(["add", str(self.file1), self.category1])
        args_add_path2 = self.arg_parser.parse_args(["add", str(self.file2), self.category1, self.category2])
        args_add_path3 = self.arg_parser.parse_args(["add", str(self.file3), self.category2])
        self.assertEqual(cli(args_add_path1), 0)
        self.assertEqual(cli(args_add_path2), 0)
        self.assertEqual(cli(args_add_path3), 0)

        args_add_symlink_without_option = self.arg_parser.parse_args(["add", str(self.file1_symlink), self.category1])
        with self.assertRaises(Exception):
            cli(args_add_symlink_without_option)

        args_add_not_exist = self.arg_parser.parse_args(['add', str(self.not_exists), self.category1])
        with self.assertRaises(Exception):
            cli(args_add_not_exist)

        args_remove_path1 = self.arg_parser.parse_args(["remove", str(self.file1), self.category1])
        args_remove_path2 = self.arg_parser.parse_args(["remove", str(self.file2), self.category2])
        self.assertEqual(cli(args_remove_path1), 0)
        self.assertEqual(cli(args_remove_path2), 0)
        args_remove_not_exist = self.arg_parser.parse_args(['remove', str(self.not_exists), self.category1])
        with self.assertRaises(Exception):
            cli(args_remove_not_exist)

        args_add_symlink = self.arg_parser.parse_args(["add", '-s', str(self.file1_symlink), self.category1])
        self.assertEqual(cli(args_add_symlink), 0)
        config = load_config(self.config_path)
        self.assertDictEqual(config, {
            self.category1: [self.file2, self.file1_symlink],
            self.category2: [self.file3]
        })

    def test_autoadd(self):
        args_add_path1 = self.arg_parser.parse_args(['-c', str(self.template_config_path), 'add', str(self.file1), self.category1])
        args_add_path2 = self.arg_parser.parse_args(['-c', str(self.template_config_path), 'add', str(self.file2), self.category1, self.category2])
        args_add_path3 = self.arg_parser.parse_args(['-c', str(self.template_config_path), 'add', str(self.file3), self.category2])
        args_add_symlink = self.arg_parser.parse_args(['-c', str(self.template_config_path), "add", '-s', str(self.file1_symlink), self.category2])
        self.assertEqual(cli(args_add_path1), 0)
        self.assertEqual(cli(args_add_path2), 0)
        self.assertEqual(cli(args_add_path3), 0)
        self.assertEqual(cli(args_add_symlink), 0)

        args_autoadd_symlink_error = self.arg_parser.parse_args(['autoadd', str(self.template_config_path)])
        with self.assertRaises(Exception):
            cli(args_autoadd_symlink_error)
        run_command(f'rm {self.file3}', check=True)
        args_autoadd_with_symlink = self.arg_parser.parse_args(['autoadd', '-s', str(self.template_config_path)])
        self.assertEqual(cli(args_autoadd_with_symlink), 0)
        config = load_config(self.config_path)
        self.assertDictEqual(config, {
            self.category1: [self.file1, self.file2],
            self.category2: [self.file2, self.file1_symlink]
        })

        run_command(f'rm {self.file1_symlink}', check=True)
        run_command(f'rm {self.config_path}', check=True)
        args_autoadd = self.arg_parser.parse_args(['autoadd', str(self.template_config_path)])
        self.assertEqual(cli(args_autoadd), 0)
        config = load_config(self.config_path)
        self.assertDictEqual(config, {
            self.category1: [self.file1, self.file2],
            self.category2: [self.file2]
        })


    def test_search_symlinks(self):
        subdir = self.root_path / 'example'
        subdir.mkdir(parents=True)
        nested_symlink = subdir / 'file2-symlink'
        nested_symlink.symlink_to(self.file2)
        expected_symlinks = set([self.file1_symlink, nested_symlink])
        actual_symlinks = set([ symlink for symlink in search_symlinks_in_directory(self.root_path)])
        self.assertSetEqual(expected_symlinks, actual_symlinks)

    def test_validate(self):
        args_add_path1 = self.arg_parser.parse_args(["add", str(self.file1), self.category1])
        args_add_path2 = self.arg_parser.parse_args(["add", str(self.file2), self.category1, self.category2])
        args_add_path3 = self.arg_parser.parse_args(["add", str(self.file3), self.category2])
        self.assertEqual(cli(args_add_path1), 0)
        self.assertEqual(cli(args_add_path2), 0)
        self.assertEqual(cli(args_add_path3), 0)

        args_validate = self.arg_parser.parse_args(['validate'])
        self.assertEqual(cli(args_validate), 0)
        run_command(f'rm "{self.file1}"', check=True)
        with self.assertRaises(Exception):
            cli(args_validate)

    def test_apply(self):
        args_add_path1 = self.arg_parser.parse_args(["add", str(self.file1), self.category1])
        args_add_path2 = self.arg_parser.parse_args(["add", str(self.file2), self.category1, self.category2])
        args_add_path3 = self.arg_parser.parse_args(["add", str(self.file3), self.category2])
        self.assertEqual(cli(args_add_path1), 0)
        self.assertEqual(cli(args_add_path2), 0)
        self.assertEqual(cli(args_add_path3), 0)

        self.assertFalse(self.side_effect_file.exists())
        args_apply = self.arg_parser.parse_args(['apply', str(self.operation_file)])
        self.assertEqual(cli(args_apply), 0)
        side_effect_file_contents = None
        with open(self.side_effect_file) as f:
            side_effect_file_contents = f.read()
        get_logger().info(side_effect_file_contents)




if __name__ == "__main__":
    unittest.main()

# TODO fix git-repotag, git-migrate & git monkeypatch
# path resolution