import os
import textwrap

import pytest

from conans.test.utils.tools import TestClient

@pytest.mark.parametrize(
    "find_package_prefer_config", ["ON", "OFF", "", None],
)
@pytest.mark.parametrize(
    "config_name_consumer", ["Findhello.cmake", "hello-config.cmake"]
)
@pytest.mark.parametrize(
    "config_name_hello", ["Findhello.cmake", "hello-config.cmake"]
)
@pytest.mark.parametrize(
    "cmake_path_mode", ["PREPEND", "APPEND", None]
)
@pytest.mark.parametrize(
    "cmake_subfolder", ["cmake",
                        "anyothername",
                        os.path.join("lib", "cmake"),
                        "lib",
                        "hello",
                        os.path.join("hello", "cmake")
                        ]
)
def test_cmaketoolchain_path_find_package_real_config_default(config_name_hello, config_name_consumer, find_package_prefer_config, cmake_path_mode,cmake_subfolder):
    client = TestClient(path_with_spaces=False)
    find_hello = textwrap.dedent("""
        MESSAGE(STATUS "hello from {component}:{filename}")
        """)
    conanfile_hello = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import copy
        class TestConan(ConanFile):
            name = "hello"
            version = "0.1"
            exports_sources = "*"
            def package(self):
                copy(self, "*", self.source_folder, self.package_folder)
            def package_info(self):
                self.cpp_info.builddirs.append("{subfolder}")
        """.format(subfolder=cmake_subfolder))
    conanfile_consumer = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake, CMakeToolchain
        import os
        class TestConan(ConanFile):
            name = "consumer"
            version = "1.0.0"
            settings = "os", "compiler", "build_type", "arch"
            exports_sources = "*"
            requires = "hello/0.1@"

            def generate(self):
                tc = CMakeToolchain(self)
                if "{value}" in ["ON","OFF",""]:
                    tc.blocks["find_paths"].values["find_package_prefer_config"] = "{value}"
                tc.generate()

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.install()
        """.format(value=find_package_prefer_config))

    if cmake_path_mode in ["APPEND","PREPEND"]:
        list_cmd = textwrap.dedent("""
            list({mode} CMAKE_MODULE_PATH ${CMAKE_CURRENT_SOURCE_DIR}/mymodules)
            list({mode} CMAKE_PREFIX_PATH ${CMAKE_CURRENT_SOURCE_DIR}/mymodules)
            """.replace("{mode}", str(cmake_path_mode)))
    else:
        list_cmd = ""

    cmake_consumer = textwrap.dedent("""\
        cmake_minimum_required(VERSION 3.15)
        project(MyHello CXX)
        %s
        message(STATUS "CMAKE_FIND_PACKAGE_PREFER_CONFIG '${CMAKE_FIND_PACKAGE_PREFER_CONFIG}'")
        message(STATUS "CMAKE_MODULE_PATH '${CMAKE_MODULE_PATH}'")
        message(STATUS "CMAKE_PREFIX_PATH '${CMAKE_PREFIX_PATH}'")
        set(CMAKE_FIND_DEBUG_MODE TRUE)
        find_package(hello REQUIRED)
        """ % list_cmd)

    client.save({"hello/conanfile.py": conanfile_hello,
                 "hello/%s/%s" % (cmake_subfolder, config_name_hello): find_hello.format(component="hello", filename=config_name_hello),
                 "consumer/conanfile.py": conanfile_consumer,
                 "consumer/CMakeLists.txt": cmake_consumer,
                 "consumer/mymodules/%s" % config_name_consumer: find_hello.format(component="consumer", filename=config_name_consumer),
                 })

    client.run("export hello")
    client.run("create consumer --build=missing")

    filenames = (config_name_hello, config_name_consumer)
    if cmake_path_mode == "PREPEND":
        if config_name_hello == config_name_consumer:
            expected_component = "consumer" # consumer path was prepended
        if find_package_prefer_config == "ON":
            if filenames == ("hello-config.cmake", "Findhello.cmake"):
                expected_component = "hello"
            elif filenames == ("Findhello.cmake", "hello-config.cmake"):
                expected_component = "consumer"
        else: # OFF = same as default behavior
            if filenames == ("hello-config.cmake", "Findhello.cmake"):
                expected_component = "consumer"
            elif filenames == ("Findhello.cmake", "hello-config.cmake"):
                expected_component = "hello"
    elif cmake_path_mode == "APPEND":
        if config_name_hello == config_name_consumer:
            expected_component = "hello" # consumer path was appended
        if find_package_prefer_config == "ON":
            if filenames == ("hello-config.cmake", "Findhello.cmake"):
                expected_component = "hello"
            elif filenames == ("Findhello.cmake", "hello-config.cmake"):
                expected_component = "consumer"
        else: # OFF = same as default behavior
            if filenames == ("hello-config.cmake", "Findhello.cmake"):
                expected_component = "consumer"
            elif filenames == ("Findhello.cmake", "hello-config.cmake"):
                expected_component = "hello"
    elif cmake_path_mode == None:
        expected_component = "hello" # nothing from consumer is found

    expected_filename = config_name_hello if (expected_component == "hello") else config_name_consumer
    assert "hello from {}:{}".format(expected_component, expected_filename) in client.out
    
    if find_package_prefer_config in ["ON", "OFF"]:
        assert "CMAKE_FIND_PACKAGE_PREFER_CONFIG '%s'" % find_package_prefer_config
    else:
        assert "CMAKE_FIND_PACKAGE_PREFER_CONFIG ''"
