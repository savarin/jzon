const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    // Default to release-fast for performance
    const optimize = b.standardOptimizeOption(.{ .preferred_optimize_mode = .ReleaseFast });

    // Build shared library for Python bindings
    const lib = b.addSharedLibrary(.{
        .name = "jzon_zig",
        .root_source_file = b.path("bindings/jzon.zig"),
        .target = target,
        .optimize = optimize,
        .version = std.SemanticVersion{ .major = 0, .minor = 1, .patch = 0 },
    });

    // Force C ABI for Python compatibility
    lib.linkLibC();
    
    // Install the library
    b.installArtifact(lib);

    // Create test executable for Zig-only testing
    const tests = b.addTest(.{
        .root_source_file = b.path("bindings/jzon.zig"),
        .target = target,
        .optimize = optimize,
    });

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
    b.installArtifact(benchmark);
    
    // Development build step for quick iteration
    const dev_lib = b.addSharedLibrary(.{
        .name = "jzon_zig",
        .root_source_file = b.path("bindings/jzon.zig"), 
        .target = target,
        .optimize = .Debug,
    });
    dev_lib.linkLibC();
    
    const dev_step = b.step("dev", "Build debug version for development");
    dev_step.dependOn(&b.addInstallArtifact(dev_lib, .{}).step);
}