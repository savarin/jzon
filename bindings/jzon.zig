const std = @import("std");
const testing = std.testing;

// Error codes for C ABI
const SUCCESS = 0;
const ERROR_BUFFER_TOO_SMALL = -1;
const ERROR_INVALID_INPUT = -2;
const ERROR_PARSE_FAILED = -3;

// Export C ABI functions for Python bindings
export fn jzon_tokenize_string(input: [*:0]const u8, output_buffer: [*]u8, buffer_size: usize) callconv(.C) i32 {
    // Basic string processing - remove quotes and handle simple escapes
    const input_slice = std.mem.span(input);
    
    // Validate input format (must be quoted string)
    if (input_slice.len < 2 or input_slice[0] != '"' or input_slice[input_slice.len - 1] != '"') {
        return ERROR_INVALID_INPUT;
    }
    
    // Extract content without quotes
    const content = input_slice[1..input_slice.len - 1];
    
    // Check if output buffer is large enough
    if (content.len >= buffer_size) {
        return ERROR_BUFFER_TOO_SMALL;
    }
    
    // Simple copy for now (TODO: handle escape sequences)
    const output_slice = output_buffer[0..buffer_size];
    @memcpy(output_slice[0..content.len], content);
    output_slice[content.len] = 0; // Null terminate
    
    return SUCCESS;
}

export fn jzon_parse_number(input: [*:0]const u8, result: *f64) callconv(.C) i32 {
    const input_slice = std.mem.span(input);
    
    // Use Zig's built-in float parsing
    if (std.fmt.parseFloat(f64, input_slice)) |value| {
        result.* = value;
        return SUCCESS;
    } else |_| {
        return ERROR_PARSE_FAILED;
    }
}

export fn jzon_validate_utf8(input: [*:0]const u8, length: usize) callconv(.C) i32 {
    const input_slice = input[0..length];
    
    // Zig's UTF-8 validation
    if (std.unicode.utf8ValidateSlice(input_slice)) {
        return SUCCESS;
    } else {
        return ERROR_PARSE_FAILED;
    }
}

// Zig-only testing functions
test "basic string tokenization" {
    var buffer: [1024]u8 = undefined;
    
    // Test simple string
    const result = jzon_tokenize_string("\"hello\"", &buffer, buffer.len);
    try testing.expect(result == SUCCESS);
    try testing.expectEqualStrings("hello", std.mem.sliceTo(&buffer, 0));
    
    // Test empty string
    const result2 = jzon_tokenize_string("\"\"", &buffer, buffer.len);
    try testing.expect(result2 == SUCCESS);
    try testing.expectEqualStrings("", std.mem.sliceTo(&buffer, 0));
    
    // Test invalid input (no quotes)
    const result3 = jzon_tokenize_string("hello", &buffer, buffer.len);
    try testing.expect(result3 == ERROR_INVALID_INPUT);
}

test "number parsing accuracy" {
    var result: f64 = undefined;
    
    // Test integer
    const status1 = jzon_parse_number("42", &result);
    try testing.expect(status1 == SUCCESS);
    try testing.expect(result == 42.0);
    
    // Test float
    const status2 = jzon_parse_number("3.14159", &result);
    try testing.expect(status2 == SUCCESS);
    try testing.expect(std.math.approxEqAbs(f64, result, 3.14159, 0.00001));
    
    // Test negative number
    const status3 = jzon_parse_number("-123.45", &result);
    try testing.expect(status3 == SUCCESS);
    try testing.expect(std.math.approxEqAbs(f64, result, -123.45, 0.00001));
    
    // Test invalid number
    const status4 = jzon_parse_number("not_a_number", &result);
    try testing.expect(status4 == ERROR_PARSE_FAILED);
}

test "utf8 validation" {
    // Test valid ASCII
    const result1 = jzon_validate_utf8("hello", 5);
    try testing.expect(result1 == SUCCESS);
    
    // Test valid UTF-8 (emoji)
    const emoji = "👋";
    const result2 = jzon_validate_utf8(emoji.ptr, emoji.len);
    try testing.expect(result2 == SUCCESS);
    
    // Test valid UTF-8 (accented characters)
    const accented = "café";
    const result3 = jzon_validate_utf8(accented.ptr, accented.len);
    try testing.expect(result3 == SUCCESS);
}