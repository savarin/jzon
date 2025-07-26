const std = @import("std");

// Fixed-size result to avoid allocation overhead
pub const ArrayResult = extern struct {
    values: [100]f64,  // Support up to 100 numbers
    count: u32,
    success: bool,
};

// Single export - parse small numeric array
export fn parse_simple_array(input: [*]const u8, len: usize, result: *ArrayResult) void {
    result.count = 0;
    result.success = false;
    
    var pos: usize = 0;
    
    // Skip whitespace
    while (pos < len and isWhitespace(input[pos])) : (pos += 1) {}
    
    // Expect '['
    if (pos >= len or input[pos] != '[') return;
    pos += 1;
    
    while (pos < len) {
        // Skip whitespace
        while (pos < len and isWhitespace(input[pos])) : (pos += 1) {}
        
        // Check for end of array
        if (pos < len and input[pos] == ']') {
            pos += 1;
            break;
        }
        
        // Parse number
        const num_start = pos;
        
        // Optional minus
        if (pos < len and input[pos] == '-') pos += 1;
        
        // Must have at least one digit
        if (pos >= len or !isDigit(input[pos])) return;
        
        // Skip digits
        while (pos < len and isDigit(input[pos])) : (pos += 1) {}
        
        // Decimal part
        if (pos < len and input[pos] == '.') {
            pos += 1;
            if (pos >= len or !isDigit(input[pos])) return;
            while (pos < len and isDigit(input[pos])) : (pos += 1) {}
        }
        
        // Exponent part
        if (pos < len and (input[pos] == 'e' or input[pos] == 'E')) {
            pos += 1;
            if (pos < len and (input[pos] == '+' or input[pos] == '-')) pos += 1;
            if (pos >= len or !isDigit(input[pos])) return;
            while (pos < len and isDigit(input[pos])) : (pos += 1) {}
        }
        
        // Convert to float
        const num_slice = input[num_start..pos];
        result.values[result.count] = std.fmt.parseFloat(f64, num_slice) catch return;
        result.count += 1;
        
        if (result.count >= 100) return; // Buffer full
        
        // Skip whitespace
        while (pos < len and isWhitespace(input[pos])) : (pos += 1) {}
        
        // Check for comma or end
        if (pos < len and input[pos] == ',') {
            pos += 1;
        } else if (pos < len and input[pos] == ']') {
            pos += 1;
            break;
        } else {
            return;
        }
    }
    
    // Skip trailing whitespace
    while (pos < len and isWhitespace(input[pos])) : (pos += 1) {}
    
    // Verify no trailing data
    if (pos == len) {
        result.success = true;
    }
}

fn isWhitespace(c: u8) bool {
    return c == ' ' or c == '\t' or c == '\n' or c == '\r';
}

fn isDigit(c: u8) bool {
    return c >= '0' and c <= '9';
}

// Validation function for build testing
export fn validate_parser() i32 {
    const test_input = "[1, 2, 3.14, -42, 1.23e-4]";
    var result: ArrayResult = undefined;
    
    parse_simple_array(test_input.ptr, test_input.len, &result);
    
    if (!result.success) return -1;
    if (result.count != 5) return -2;
    if (result.values[0] != 1.0) return -3;
    if (result.values[1] != 2.0) return -4;
    if (@abs(result.values[2] - 3.14) > 0.001) return -5;
    if (result.values[3] != -42.0) return -6;
    if (@abs(result.values[4] - 0.000123) > 0.000001) return -7;
    
    return 0;
}