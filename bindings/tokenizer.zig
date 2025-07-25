const std = @import("std");
const testing = std.testing;

// Error codes for C ABI
const SUCCESS = 0;
const ERROR_BUFFER_TOO_SMALL = -1;
const ERROR_INVALID_INPUT = -2;
const ERROR_PARSE_FAILED = -3;
const ERROR_UNTERMINATED_STRING = -4;
const ERROR_INVALID_ESCAPE = -5;
const ERROR_INVALID_UNICODE = -6;

// Token types matching Python ParseState enum
const TokenType = enum(c_int) {
    NONE = 0,
    OBJECT_START = 1,
    OBJECT_END = 2,
    ARRAY_START = 3,
    ARRAY_END = 4,
    STRING = 5,
    NUMBER = 6,
    BOOLEAN = 7,
    NULL = 8,
    COMMA = 9,
    COLON = 10,
    EOF = 11,
    ERROR = 12,
};

// Token structure for C ABI
const JsonToken = extern struct {
    token_type: TokenType,
    start_pos: u32,
    end_pos: u32,
    // Additional fields can be added for token value if needed
};

// Tokenizer state structure
const TokenizerState = struct {
    text: []const u8,
    pos: u32,
    length: u32,
    
    fn init(text: []const u8) TokenizerState {
        return TokenizerState{
            .text = text,
            .pos = 0,
            .length = @intCast(text.len),
        };
    }
    
    fn peek(self: *const TokenizerState) u8 {
        if (self.pos >= self.length) return 0;
        return self.text[self.pos];
    }
    
    fn advance(self: *TokenizerState) u8 {
        if (self.pos >= self.length) return 0;
        const char = self.text[self.pos];
        self.pos += 1;
        return char;
    }
    
    fn isAtEnd(self: *const TokenizerState) bool {
        return self.pos >= self.length;
    }
    
    fn skipWhitespace(self: *TokenizerState) void {
        while (!self.isAtEnd()) {
            const char = self.peek();
            if (char == ' ' or char == '\t' or char == '\n' or char == '\r') {
                _ = self.advance();
            } else {
                break;
            }
        }
    }
    
    fn scanString(self: *TokenizerState, start_pos: u32) !JsonToken {
        // Skip opening quote
        _ = self.advance();
        
        while (!self.isAtEnd()) {
            const char = self.advance();
            if (char == '"') {
                return JsonToken{
                    .token_type = TokenType.STRING,
                    .start_pos = start_pos,
                    .end_pos = self.pos,
                };
            } else if (char == '\\') {
                // Handle escape sequences
                if (self.isAtEnd()) {
                    return error.UnterminatedString;
                }
                const escaped = self.advance();
                switch (escaped) {
                    '"', '\\', '/', 'b', 'f', 'n', 'r', 't' => {},
                    'u' => {
                        // Unicode escape sequence: \uXXXX
                        var i: u8 = 0;
                        while (i < 4) : (i += 1) {
                            if (self.isAtEnd()) {
                                return error.InvalidUnicodeEscape;
                            }
                            const hex_char = self.advance();
                            if (!isHexDigit(hex_char)) {
                                return error.InvalidUnicodeEscape;
                            }
                        }
                    },
                    else => {
                        return error.InvalidEscapeSequence;
                    },
                }
            } else if (char == '\n' or char == '\r') {
                return error.UnterminatedString;
            }
        }
        
        return error.UnterminatedString;
    }
    
    fn scanNumber(self: *TokenizerState, start_pos: u32) JsonToken {
        // Handle optional minus
        var has_minus = false;
        if (self.peek() == '-') {
            has_minus = true;
            _ = self.advance();
        }
        
        // Check for -Infinity
        if (has_minus and self.peek() == 'I') {
            // Try to match "Infinity"
            const saved_pos = self.pos;
            const remaining = self.text[self.pos..];
            if (remaining.len >= 8 and std.mem.eql(u8, remaining[0..8], "Infinity")) {
                self.pos += 8;
                return JsonToken{
                    .token_type = TokenType.BOOLEAN, // Treat as special literal
                    .start_pos = start_pos,
                    .end_pos = self.pos,
                };
            } else {
                self.pos = saved_pos; // Reset position
            }
        }
        
        // Handle integer part
        if (self.peek() == '0') {
            _ = self.advance();
            // Leading zeros not allowed except for single zero
            if (isDigit(self.peek())) {
                return JsonToken{
                    .token_type = TokenType.ERROR,
                    .start_pos = start_pos,
                    .end_pos = self.pos,
                };
            }
        } else if (isDigit(self.peek())) {
            while (isDigit(self.peek())) {
                _ = self.advance();
            }
        } else {
            return JsonToken{
                .token_type = TokenType.ERROR,
                .start_pos = start_pos,
                .end_pos = self.pos,
            };
        }
        
        // Handle fractional part
        if (self.peek() == '.') {
            _ = self.advance();
            if (!isDigit(self.peek())) {
                return JsonToken{
                    .token_type = TokenType.ERROR,
                    .start_pos = start_pos,
                    .end_pos = self.pos,
                };
            }
            while (isDigit(self.peek())) {
                _ = self.advance();
            }
        }
        
        // Handle exponent part
        if (self.peek() == 'e' or self.peek() == 'E') {
            _ = self.advance();
            if (self.peek() == '+' or self.peek() == '-') {
                _ = self.advance();
            }
            if (!isDigit(self.peek())) {
                return JsonToken{
                    .token_type = TokenType.ERROR,
                    .start_pos = start_pos,
                    .end_pos = self.pos,
                };
            }
            while (isDigit(self.peek())) {
                _ = self.advance();
            }
        }
        
        return JsonToken{
            .token_type = TokenType.NUMBER,
            .start_pos = start_pos,
            .end_pos = self.pos,
        };
    }
    
    fn scanLiteral(self: *TokenizerState, start_pos: u32, literal: []const u8, token_type: TokenType) JsonToken {
        var i: usize = 0;
        while (i < literal.len and !self.isAtEnd()) {
            if (self.advance() != literal[i]) {
                return JsonToken{
                    .token_type = TokenType.ERROR,
                    .start_pos = start_pos,
                    .end_pos = self.pos,
                };
            }
            i += 1;
        }
        
        if (i == literal.len) {
            return JsonToken{
                .token_type = token_type,
                .start_pos = start_pos,
                .end_pos = self.pos,
            };
        } else {
            return JsonToken{
                .token_type = TokenType.ERROR,
                .start_pos = start_pos,
                .end_pos = self.pos,
            };
        }
    }
    
    fn scanIdentifier(self: *TokenizerState, start_pos: u32) JsonToken {
        // Scan identifier-like tokens (true, false, null, Infinity, NaN)
        while (!self.isAtEnd()) {
            const char = self.peek();
            if (isAlpha(char)) {
                _ = self.advance();
            } else {
                break;
            }
        }
        
        const identifier = self.text[start_pos..self.pos];
        
        if (std.mem.eql(u8, identifier, "true") or std.mem.eql(u8, identifier, "false")) {
            return JsonToken{
                .token_type = TokenType.BOOLEAN,
                .start_pos = start_pos,
                .end_pos = self.pos,
            };
        } else if (std.mem.eql(u8, identifier, "null")) {
            return JsonToken{
                .token_type = TokenType.NULL,
                .start_pos = start_pos,
                .end_pos = self.pos,
            };
        } else if (std.mem.eql(u8, identifier, "Infinity") or std.mem.eql(u8, identifier, "NaN")) {
            return JsonToken{
                .token_type = TokenType.BOOLEAN, // Treat as special literals
                .start_pos = start_pos,
                .end_pos = self.pos,
            };
        } else {
            return JsonToken{
                .token_type = TokenType.ERROR,
                .start_pos = start_pos,
                .end_pos = self.pos,
            };
        }
    }
    
    fn nextToken(self: *TokenizerState) !JsonToken {
        self.skipWhitespace();
        
        if (self.isAtEnd()) {
            return JsonToken{
                .token_type = TokenType.EOF,
                .start_pos = self.pos,
                .end_pos = self.pos,
            };
        }
        
        const start_pos = self.pos;
        const char = self.peek();
        
        switch (char) {
            '{' => {
                _ = self.advance();
                return JsonToken{
                    .token_type = TokenType.OBJECT_START,
                    .start_pos = start_pos,
                    .end_pos = self.pos,
                };
            },
            '}' => {
                _ = self.advance();
                return JsonToken{
                    .token_type = TokenType.OBJECT_END,
                    .start_pos = start_pos,
                    .end_pos = self.pos,
                };
            },
            '[' => {
                _ = self.advance();
                return JsonToken{
                    .token_type = TokenType.ARRAY_START,
                    .start_pos = start_pos,
                    .end_pos = self.pos,
                };
            },
            ']' => {
                _ = self.advance();
                return JsonToken{
                    .token_type = TokenType.ARRAY_END,
                    .start_pos = start_pos,
                    .end_pos = self.pos,
                };
            },
            ',' => {
                _ = self.advance();
                return JsonToken{
                    .token_type = TokenType.COMMA,
                    .start_pos = start_pos,
                    .end_pos = self.pos,
                };
            },
            ':' => {
                _ = self.advance();
                return JsonToken{
                    .token_type = TokenType.COLON,
                    .start_pos = start_pos,
                    .end_pos = self.pos,
                };
            },
            '"' => {
                return self.scanString(start_pos);
            },
            '-', '0'...'9' => {
                return self.scanNumber(start_pos);
            },
            't', 'f', 'n', 'I', 'N' => {
                return self.scanIdentifier(start_pos);
            },
            else => {
                _ = self.advance();
                return JsonToken{
                    .token_type = TokenType.ERROR,
                    .start_pos = start_pos,
                    .end_pos = self.pos,
                };
            },
        }
    }
};

// Helper functions
fn isDigit(char: u8) bool {
    return char >= '0' and char <= '9';
}

fn isHexDigit(char: u8) bool {
    return (char >= '0' and char <= '9') or
           (char >= 'a' and char <= 'f') or
           (char >= 'A' and char <= 'F');
}

fn isAlpha(char: u8) bool {
    return (char >= 'a' and char <= 'z') or
           (char >= 'A' and char <= 'Z');
}

// C ABI exports for Python integration
export fn jzon_next_token(
    text: [*:0]const u8,
    text_length: u32,
    position: *u32,
    token_out: *JsonToken
) callconv(.C) i32 {
    const input_slice = text[0..text_length];
    
    var state = TokenizerState.init(input_slice);
    state.pos = position.*;
    
    const token = state.nextToken() catch |err| {
        return switch (err) {
            error.UnterminatedString => ERROR_UNTERMINATED_STRING,
            error.InvalidEscapeSequence => ERROR_INVALID_ESCAPE,
            error.InvalidUnicodeEscape => ERROR_INVALID_UNICODE,
        };
    };
    
    position.* = state.pos;
    token_out.* = token;
    
    return SUCCESS;
}

export fn jzon_create_tokenizer_state(text: [*:0]const u8, text_length: u32) callconv(.C) ?*TokenizerState {
    const allocator = std.heap.c_allocator;
    const input_slice = text[0..text_length];
    
    const state = allocator.create(TokenizerState) catch return null;
    state.* = TokenizerState.init(input_slice);
    
    return state;
}

export fn jzon_destroy_tokenizer_state(state: *TokenizerState) callconv(.C) void {
    const allocator = std.heap.c_allocator;
    allocator.destroy(state);
}

export fn jzon_tokenizer_next_token(state: *TokenizerState, token_out: *JsonToken) callconv(.C) i32 {
    const token = state.nextToken() catch |err| {
        return switch (err) {
            error.UnterminatedString => ERROR_UNTERMINATED_STRING,
            error.InvalidEscapeSequence => ERROR_INVALID_ESCAPE,
            error.InvalidUnicodeEscape => ERROR_INVALID_UNICODE,
        };
    };
    
    token_out.* = token;
    return SUCCESS;
}

// String processing function with full escape sequence handling
export fn jzon_process_string_escapes(
    input: [*:0]const u8,
    input_length: u32,
    output_buffer: [*]u8,
    buffer_size: u32,
    output_length: *u32
) callconv(.C) i32 {
    const input_slice = input[0..input_length];
    const output_slice = output_buffer[0..buffer_size];
    
    // Validate input format (must be quoted string)
    if (input_slice.len < 2 or input_slice[0] != '"' or input_slice[input_slice.len - 1] != '"') {
        return ERROR_INVALID_INPUT;
    }
    
    // Extract content without quotes
    const content = input_slice[1..input_slice.len - 1];
    var output_pos: u32 = 0;
    var i: u32 = 0;
    
    while (i < content.len) {
        if (output_pos >= buffer_size) {
            return ERROR_BUFFER_TOO_SMALL;
        }
        
        if (content[i] == '\\' and i + 1 < content.len) {
            const escaped = content[i + 1];
            switch (escaped) {
                '"' => {
                    output_slice[output_pos] = '"';
                    output_pos += 1;
                    i += 2;
                },
                '\\' => {
                    output_slice[output_pos] = '\\';
                    output_pos += 1;
                    i += 2;
                },
                '/' => {
                    output_slice[output_pos] = '/';
                    output_pos += 1;
                    i += 2;
                },
                'b' => {
                    output_slice[output_pos] = '\x08'; // backspace
                    output_pos += 1;
                    i += 2;
                },
                'f' => {
                    output_slice[output_pos] = '\x0C'; // form feed
                    output_pos += 1;
                    i += 2;
                },
                'n' => {
                    output_slice[output_pos] = '\n';
                    output_pos += 1;
                    i += 2;
                },
                'r' => {
                    output_slice[output_pos] = '\r';
                    output_pos += 1;
                    i += 2;
                },
                't' => {
                    output_slice[output_pos] = '\t';
                    output_pos += 1;
                    i += 2;
                },
                'u' => {
                    // Unicode escape sequence: \uXXXX
                    if (i + 5 >= content.len) {
                        return ERROR_INVALID_UNICODE;
                    }
                    
                    const hex_digits = content[i+2..i+6];
                    var unicode_value: u16 = 0;
                    
                    for (hex_digits) |hex_char| {
                        if (!isHexDigit(hex_char)) {
                            return ERROR_INVALID_UNICODE;
                        }
                        unicode_value = unicode_value * 16 + hexDigitValue(hex_char);
                    }
                    
                    // Convert Unicode code point to UTF-8
                    var utf8_buffer: [4]u8 = undefined;
                    const utf8_len = std.unicode.utf8Encode(unicode_value, &utf8_buffer) catch {
                        return ERROR_INVALID_UNICODE;
                    };
                    
                    if (output_pos + utf8_len > buffer_size) {
                        return ERROR_BUFFER_TOO_SMALL;
                    }
                    
                    @memcpy(output_slice[output_pos..output_pos + utf8_len], utf8_buffer[0..utf8_len]);
                    output_pos += @intCast(utf8_len);
                    i += 6;
                },
                else => {
                    return ERROR_INVALID_ESCAPE;
                },
            }
        } else {
            output_slice[output_pos] = content[i];
            output_pos += 1;
            i += 1;
        }
    }
    
    output_length.* = output_pos;
    return SUCCESS;
}

fn hexDigitValue(char: u8) u16 {
    return switch (char) {
        '0'...'9' => char - '0',
        'a'...'f' => char - 'a' + 10,
        'A'...'F' => char - 'A' + 10,
        else => 0,
    };
}

// Legacy functions for backward compatibility
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
test "tokenizer basic tokens" {
    const text = "{}[],:";
    var state = TokenizerState.init(text);
    
    // Test object start
    var token = try state.nextToken();
    try testing.expect(token.token_type == TokenType.OBJECT_START);
    try testing.expect(token.start_pos == 0);
    try testing.expect(token.end_pos == 1);
    
    // Test object end
    token = try state.nextToken();
    try testing.expect(token.token_type == TokenType.OBJECT_END);
    
    // Test array start
    token = try state.nextToken();
    try testing.expect(token.token_type == TokenType.ARRAY_START);
    
    // Test array end
    token = try state.nextToken();
    try testing.expect(token.token_type == TokenType.ARRAY_END);
    
    // Test comma
    token = try state.nextToken();
    try testing.expect(token.token_type == TokenType.COMMA);
    
    // Test colon
    token = try state.nextToken();
    try testing.expect(token.token_type == TokenType.COLON);
    
    // Test EOF
    token = try state.nextToken();
    try testing.expect(token.token_type == TokenType.EOF);
}

test "tokenizer string handling" {
    const text = "\"hello world\" \"with\\\"quotes\" \"unicode\\u0041\"";
    var state = TokenizerState.init(text);
    
    // Test simple string
    var token = try state.nextToken();
    try testing.expect(token.token_type == TokenType.STRING);
    try testing.expect(token.start_pos == 0);
    try testing.expect(token.end_pos == 13);
    
    // Test string with escape
    token = try state.nextToken();
    try testing.expect(token.token_type == TokenType.STRING);
    
    // Test unicode escape
    token = try state.nextToken();
    try testing.expect(token.token_type == TokenType.STRING);
}

test "tokenizer number handling" {
    const text = "42 -17 3.14159 -2.5e-10";
    var state = TokenizerState.init(text);
    
    // Test positive integer
    var token = try state.nextToken();
    try testing.expect(token.token_type == TokenType.NUMBER);
    
    // Test negative integer
    token = try state.nextToken();
    try testing.expect(token.token_type == TokenType.NUMBER);
    
    // Test decimal
    token = try state.nextToken();
    try testing.expect(token.token_type == TokenType.NUMBER);
    
    // Test scientific notation
    token = try state.nextToken();
    try testing.expect(token.token_type == TokenType.NUMBER);
}

test "tokenizer literal handling" {
    const text = "true false null";
    var state = TokenizerState.init(text);
    
    // Test true
    var token = try state.nextToken();
    try testing.expect(token.token_type == TokenType.BOOLEAN);
    
    // Test false
    token = try state.nextToken();
    try testing.expect(token.token_type == TokenType.BOOLEAN);
    
    // Test null
    token = try state.nextToken();
    try testing.expect(token.token_type == TokenType.NULL);
}

test "string escape processing" {
    var output_buffer: [1024]u8 = undefined;
    var output_length: u32 = undefined;
    
    // Test simple escapes
    const result1 = jzon_process_string_escapes(
        "\"hello\\nworld\"",
        14,
        &output_buffer,
        output_buffer.len,
        &output_length
    );
    
    try testing.expect(result1 == SUCCESS);
    try testing.expect(output_length == 11);
    try testing.expectEqualStrings("hello\nworld", output_buffer[0..output_length]);
    
    // Test unicode escape
    const result2 = jzon_process_string_escapes(
        "\"\\u0041\"",
        8,
        &output_buffer,
        output_buffer.len,
        &output_length
    );
    
    try testing.expect(result2 == SUCCESS);
    try testing.expect(output_length == 1);
    try testing.expectEqualStrings("A", output_buffer[0..output_length]);
}

test "error handling" {
    var state = TokenizerState.init("\"unterminated string");
    
    // Test unterminated string
    const token_result = state.nextToken();
    try testing.expectError(error.UnterminatedString, token_result);
    
    // Test invalid escape
    state = TokenizerState.init("\"\\q\"");
    const escape_result = state.nextToken();
    try testing.expectError(error.InvalidEscapeSequence, escape_result);
}