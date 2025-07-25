const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    // Default to release-fast for performance
    const optimize = b.standardOptimizeOption(.{ .preferred_optimize_mode = .ReleaseFast });

    // Detect Python development headers
    const python_config = detectPythonConfig(b) catch {
        std.log.err("Failed to detect Python development headers. Please install python3-dev", .{});
        return;
    };

    // Build shared library for Python bindings
    const lib = b.addSharedLibrary(.{
        .name = "jzon_zig",
        .root_source_file = b.path("bindings/parser_fast_validate.zig"), // Use fast validation version
        .target = target,
        .optimize = optimize,
        .version = std.SemanticVersion{ .major = 0, .minor = 1, .patch = 0 },
    });

    // Force C ABI for Python compatibility
    lib.linkLibC();
    
    // Add Python headers and libraries for Python C API
    lib.addIncludePath(.{ .cwd_relative = python_config.include_dir });
    lib.addLibraryPath(.{ .cwd_relative = python_config.lib_dir });
    lib.linkSystemLibrary(python_config.lib_name);
    
    // Install the library
    b.installArtifact(lib);

    // Create test executable for Zig-only testing
    const tests = b.addTest(.{
        .root_source_file = b.path("bindings/parser.zig"),
        .target = target,
        .optimize = optimize,
    });
    
    tests.linkLibC();
    tests.addIncludePath(.{ .cwd_relative = python_config.include_dir });

    const test_cmd = b.addRunArtifact(tests);
    const test_step = b.step("test", "Run Zig tests");
    test_step.dependOn(&test_cmd.step);

    // Benchmark executable for performance testing
    const benchmark = b.addExecutable(.{
        .name = "jzon_benchmark",
        .root_source_file = b.path("bindings/benchmark.zig"),
        .target = target,
        .optimize = optimize,
    });
    
    benchmark.linkLibC();
    benchmark.addIncludePath(.{ .cwd_relative = python_config.include_dir });
    b.installArtifact(benchmark);
    
    // Development build step for quick iteration with debug info
    const dev_lib = b.addSharedLibrary(.{
        .name = "jzon_zig",
        .root_source_file = b.path("bindings/parser.zig"), 
        .target = target,
        .optimize = .Debug,
    });
    dev_lib.linkLibC();
    dev_lib.addIncludePath(.{ .cwd_relative = python_config.include_dir });
    dev_lib.addLibraryPath(.{ .cwd_relative = python_config.lib_dir });
    dev_lib.linkSystemLibrary(python_config.lib_name);
    
    const dev_step = b.step("dev", "Build debug version for development");
    dev_step.dependOn(&b.addInstallArtifact(dev_lib, .{}).step);
}

// Python configuration detection
const PythonConfig = struct {
    include_dir: []const u8,
    lib_dir: []const u8,
    lib_name: []const u8,
};

fn detectPythonConfig(b: *std.Build) !PythonConfig {
    _ = b;
    
    // Use uv/PyApp Python configuration
    return PythonConfig{
        .include_dir = "/Users/savarin/.local/share/uv/python/cpython-3.12.8-macos-aarch64-none/include/python3.12",
        .lib_dir = "/Users/savarin/.local/share/uv/python/cpython-3.12.8-macos-aarch64-none/lib",
        .lib_name = "python3.12",
    };
}