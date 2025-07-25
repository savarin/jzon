const std = @import("std");

// Ultra-fast JSON validator that can pre-screen JSON before Python parsing
// Optimized for speed over detailed error reporting

const ValidationResult = enum {
    valid,
    invalid,
    complex, // Requires full parsing
};

const FastValidator = struct {
    input: []const u8,
    pos: usize,
    depth: u8,
    
    const MAX_DEPTH = 64; // Reasonable recursion limit
    
    fn init(input: []const u8) FastValidator {
        return FastValidator{
            .input = input,
            .pos = 0,
            .depth = 0,
        };
    }
    
    fn peek(self: *FastValidator) ?u8 {
        if (self.pos >= self.input.len) return null;
        return self.input[self.pos];
    }
    
    fn advance(self: *FastValidator) ?u8 {
        if (self.pos >= self.input.len) return null;
        const char = self.input[self.pos];
        self.pos += 1;
        return char;
    }
    
    fn skipWhitespace(self: *FastValidator) void {
        while (self.pos < self.input.len) {
            switch (self.input[self.pos]) {
                ' ', '\t', '\n', '\r' => self.pos += 1,
                else => break,
            }
        }
    }
    
    fn validateString(self: *FastValidator) ValidationResult {
        if (self.advance() != '"') return .invalid;
        
        while (self.pos < self.input.len) {
            const char = self.advance() orelse return .invalid;
            
            if (char == '"') {
                return .valid;
            } else if (char == '\\') {
                // Skip escaped character
                const escaped = self.advance() orelse return .invalid;
                if (escaped == 'u') {
                    // Skip 4 hex digits
                    for (0..4) |_| {
                        const hex = self.advance() orelse return .invalid;
                        if (!((hex >= '0' and hex <= '9') or 
                              (hex >= 'a' and hex <= 'f') or 
                              (hex >= 'A' and hex <= 'F'))) {
                            return .invalid;
                        }
                    }
                }
            } else if (char < 0x20) {
                return .invalid; // Control characters not allowed
            }
        }
        
        return .invalid; // Unterminated string
    }
    
    fn validateNumber(self: *FastValidator) ValidationResult {
        // Handle negative sign
        if (self.peek() == '-') {
            _ = self.advance();
        }
        
        // Must have at least one digit
        const first_digit = self.peek() orelse return .invalid;
        if (first_digit < '0' or first_digit > '9') return .invalid;
        
        // Handle leading zero case
        if (first_digit == '0') {
            _ = self.advance();
            // After 0, we can only have '.', 'e', 'E', or end
            const next_char = self.peek();
            if (next_char != null and next_char.? >= '0' and next_char.? <= '9') {
                return .invalid; // Leading zeros not allowed
            }
        } else {
            // Parse integer digits
            while (self.pos < self.input.len) {
                const char = self.peek() orelse break;
                if (char >= '0' and char <= '9') {
                    _ = self.advance();
                } else {
                    break;
                }
            }
        }
        
        // Handle decimal part
        if (self.peek() == '.') {
            _ = self.advance();
            
            // Must have at least one digit after decimal point
            if (self.peek() == null or (self.peek().? < '0' or self.peek().? > '9')) {
                return .invalid;
            }
            
            while (self.pos < self.input.len) {
                const char = self.peek() orelse break;
                if (char >= '0' and char <= '9') {
                    _ = self.advance();
                } else {
                    break;
                }
            }
        }
        
        // Handle exponent part
        if (self.peek() != null and (self.peek().? == 'e' or self.peek().? == 'E')) {
            _ = self.advance();
            
            // Handle optional + or - after e/E
            const next = self.peek();
            if (next == '+' or next == '-') {
                _ = self.advance();
            }
            
            // Must have at least one digit in exponent
            if (self.peek() == null or (self.peek().? < '0' or self.peek().? > '9')) {
                return .invalid;
            }
            
            while (self.pos < self.input.len) {
                const char = self.peek() orelse break;
                if (char >= '0' and char <= '9') {
                    _ = self.advance();
                } else {
                    break;
                }
            }
        }
        
        return .valid;
    }
    
    fn validateLiteral(self: *FastValidator, literal: []const u8) ValidationResult {
        if (self.pos + literal.len > self.input.len) return .invalid;
        
        if (std.mem.eql(u8, self.input[self.pos..self.pos + literal.len], literal)) {
            self.pos += literal.len;
            return .valid;
        }
        
        return .invalid;
    }
    
    fn validateValue(self: *FastValidator) ValidationResult {
        if (self.depth >= MAX_DEPTH) return .invalid;
        
        self.skipWhitespace();
        
        const char = self.peek() orelse return .invalid;
        
        return switch (char) {
            '{' => self.validateObject(),
            '[' => self.validateArray(),
            '"' => self.validateString(),
            't' => self.validateLiteral("true"),
            'f' => self.validateLiteral("false"),
            'n' => self.validateLiteral("null"),
            '-', '0'...'9' => self.validateNumber(),
            else => .invalid,
        };
    }
    
    fn validateObject(self: *FastValidator) ValidationResult {
        _ = self.advance(); // Skip '{'
        self.depth += 1;
        defer self.depth -= 1;
        
        self.skipWhitespace();
        
        // Handle empty object
        if (self.peek() == '}') {
            _ = self.advance();
            return .valid;
        }
        
        while (true) {
            // Parse key (must be string)
            self.skipWhitespace();
            if (self.validateString() != .valid) {
                return .invalid;
            }
            
            self.skipWhitespace();
            
            // Expect colon
            if (self.advance() != ':') return .invalid;
            
            // Parse value
            if (self.validateValue() != .valid) {
                return .invalid;
            }
            
            self.skipWhitespace();
            const next = self.peek() orelse return .invalid;
            
            if (next == '}') {
                _ = self.advance();
                break;
            } else if (next == ',') {
                _ = self.advance();
            } else {
                return .invalid;
            }
        }
        
        return .valid;
    }
    
    fn validateArray(self: *FastValidator) ValidationResult {
        _ = self.advance(); // Skip '['
        self.depth += 1;
        defer self.depth -= 1;
        
        self.skipWhitespace();
        
        // Handle empty array
        if (self.peek() == ']') {
            _ = self.advance();
            return .valid;
        }
        
        while (true) {
            if (self.validateValue() != .valid) {
                return .invalid;
            }
            
            self.skipWhitespace();
            const next = self.peek() orelse return .invalid;
            
            if (next == ']') {
                _ = self.advance();
                break;
            } else if (next == ',') {
                _ = self.advance();
            } else {
                return .invalid;
            }
        }
        
        return .valid;
    }
    
    fn validate(self: *FastValidator) ValidationResult {
        const result = self.validateValue();
        if (result != .valid) return result;
        
        self.skipWhitespace();
        
        // Should have consumed all input
        if (self.pos < self.input.len) {
            return .invalid;
        }
        
        return .valid;
    }
};

// Main validation function
export fn jzon_validate_json(
    input: [*c]const u8,
    input_len: isize,
) callconv(.C) i32 {
    if (input_len <= 0) return 0;
    
    const input_slice = input[0..@intCast(input_len)];
    var validator = FastValidator.init(input_slice);
    
    const result = validator.validate();
    return if (result == .valid) 1 else 0;
}

// Fast-path parser that only handles simple cases
export fn jzon_parse_simple(
    input: [*c]const u8,
    input_len: isize,
    config: ?*anyopaque,
    error_info: ?*anyopaque,
) callconv(.C) ?*anyopaque {
    _ = config;
    _ = error_info;
    
    // For now, just validate and return null to indicate Python fallback
    // This gives us ultra-fast validation with Python parsing
    const is_valid = jzon_validate_json(input, input_len);
    
    // Always return null for Python fallback, but validation already happened
    _ = is_valid;
    return null;
}

// Test function
export fn jzon_test_function() callconv(.C) i32 {
    return 42;
}