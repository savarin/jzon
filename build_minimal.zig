const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});
    
    // Single library with minimal dependencies - no Python integration needed
    const lib = b.addSharedLibrary(.{
        .name = "minimal_array",
        .root_source_file = b.path("bindings/minimal_array.zig"),
        .target = target,
        .optimize = optimize,
    });
    
    // Only need C ABI, no Python dependency for this test
    lib.linkLibC();
    
    b.installArtifact(lib);
    
    // Add test step to validate the parser works
    const test_step = b.step("test", "Test the minimal array parser");
    
    const test_exe = b.addExecutable(.{
        .name = "test_minimal",
        .root_source_file = b.path("bindings/minimal_array.zig"),
        .target = target,
        .optimize = optimize,
    });
    
    const test_run = b.addRunArtifact(test_exe);
    test_step.dependOn(&test_run.step);
}