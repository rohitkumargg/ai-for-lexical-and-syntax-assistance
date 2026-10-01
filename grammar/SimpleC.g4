grammar SimpleC;

/* =========================
   PARSER RULES
   ========================= */

program
    : topLevelItem+ EOF
    ;

topLevelItem
    : functionDef
    | functionDeclaration
    | declaration
    ;

// ---- Function Prototypes / Declarations ----
// Supports: int add(int a, int b); or int add(int, int); or void run(void);
functionDeclaration
    : typeSpecifier pointer? IDENTIFIER LPAREN paramList? RPAREN SEMI
    ;

// ---- Functions ----
// Supports: int foo(int a, float b) { ... }
functionDef
    : typeSpecifier pointer? IDENTIFIER LPAREN paramList? RPAREN block
    ;

paramList
    : param (COMMA param)*
    ;

param
    : typeSpecifier pointer? IDENTIFIER? arraySuffix?
    ;

// ---- Blocks with mixed declarations/statements (C99 style) ----
block
    : LBRACE blockItem* RBRACE
    ;

blockItem
    : declaration
    | statement
    ;

// ---- Declarations ----
declaration
    : declarationNoSemi SEMI
    ;

// IMPORTANT: same as declaration, but WITHOUT the trailing ';'
// Needed for: for (int i=0; ... ; ...)
declarationNoSemi
    : typeSpecifier initDeclaratorList?
    ;

initDeclaratorList
    : initDeclarator (COMMA initDeclarator)*
    ;

initDeclarator
    : pointer? IDENTIFIER arraySuffix? (ASSIGN initializer)?
    ;

initializer
    : assignmentExpression
    | LBRACE (initializer (COMMA initializer)* COMMA?)? RBRACE
    ;

// A separate rule keeps `int *p` and `int **pp` unambiguous in declarations,
// parameters, and function return types.
pointer
    : MUL+
    ;

// multi-dimensional arrays: int a[10][20][30];
arraySuffix
    : (LBRACK expression? RBRACK)+
    ;

// ---- Statements ----
statement
    : emptyStatement
    | exprStatement
    | ifStatement
    | whileStatement
    | doWhileStatement
    | forStatement
    | switchStatement
    | labeledStatement
    | returnStatement
    | breakStatement
    | continueStatement
    | block
    ;

switchStatement
    : SWITCH LPAREN expression RPAREN statement
    ;

labeledStatement
    : CASE conditionalExpression COLON
    | DEFAULT COLON
    ;

emptyStatement
    : SEMI
    ;

exprStatement
    : expression? SEMI
    ;

ifStatement
    : IF LPAREN expression RPAREN statement (ELSE statement)?
    ;

whileStatement
    : WHILE LPAREN expression RPAREN statement
    ;

doWhileStatement
    : DO statement WHILE LPAREN expression RPAREN SEMI
    ;

// for (init; cond; update) stmt
forStatement
    : FOR LPAREN forInit? SEMI expression? SEMI expression? RPAREN statement
    ;

forInit
    : declarationNoSemi
    | expression
    ;

returnStatement
    : RETURN expression? SEMI
    ;

breakStatement
    : BREAK SEMI
    ;

continueStatement
    : CONTINUE SEMI
    ;


/* =========================
   EXPRESSIONS (with precedence)
   ========================= */

expression
    : assignmentExpression (COMMA assignmentExpression)*
    ;

// assignment and compound assignment
assignmentExpression
    : conditionalExpression
    | unaryExpression assignmentOperator assignmentExpression
    ;

assignmentOperator
    : ASSIGN
    | ADD_ASSIGN
    | SUB_ASSIGN
    | MUL_ASSIGN
    | DIV_ASSIGN
    | MOD_ASSIGN
    | AND_ASSIGN
    | OR_ASSIGN
    | XOR_ASSIGN
    | LSHIFT_ASSIGN
    | RSHIFT_ASSIGN
    ;

conditionalExpression
    : logicalOrExpression (QUESTION expression COLON conditionalExpression)?
    ;

logicalOrExpression
    : logicalAndExpression (OR logicalAndExpression)*
    ;

logicalAndExpression
    : inclusiveOrExpression (AND inclusiveOrExpression)*
    ;

inclusiveOrExpression
    : exclusiveOrExpression (PIPE exclusiveOrExpression)*
    ;

exclusiveOrExpression
    : andExpression (CARET andExpression)*
    ;

andExpression
    : equalityExpression (AMP equalityExpression)*
    ;

equalityExpression
    : relationalExpression ((EQ | NEQ) relationalExpression)*
    ;

relationalExpression
    : shiftExpression ((LT | LTE | GT | GTE) shiftExpression)*
    ;

shiftExpression
    : additiveExpression ((LSHIFT | RSHIFT) additiveExpression)*
    ;

additiveExpression
    : multiplicativeExpression ((PLUS | MINUS) multiplicativeExpression)*
    ;

multiplicativeExpression
    : unaryExpression ((MUL | DIV | MOD) unaryExpression)*
    ;

// unary: ++x, --x, +x, -x, !x, ~x, &x
unaryExpression
    : postfixExpression
    | (INC | DEC | PLUS | MINUS | NOT | TILDE | AMP | MUL) unaryExpression
    // A type specifier after '(' is the clean syntactic discriminator for a cast.
    | LPAREN typeSpecifier pointer? RPAREN unaryExpression
    | SIZEOF (LPAREN typeSpecifier pointer? RPAREN | unaryExpression)
    ;

// postfix: x++, x--, calls f(a,b), array indexing a[i]
postfixExpression
    : primaryExpression postfixPart*
    ;

postfixPart
    : LBRACK expression RBRACK
    | LPAREN argumentList? RPAREN
    | DOT IDENTIFIER
    | ARROW IDENTIFIER
    | INC
    | DEC
    ;

argumentList
    : assignmentExpression (COMMA assignmentExpression)*
    ;

primaryExpression
    : IDENTIFIER
    | INTEGER
    | FLOAT_LITERAL
    | CHAR_LITERAL
    | STRING_LITERAL
    | NULL
    | LPAREN expression RPAREN
    ;


/* =========================
   TYPES
   ========================= */

typeSpecifier
    : (SIGNED | UNSIGNED)? (
          CHAR
        | SHORT INT?
        | LONG LONG INT?
        | LONG INT?
        | INT
      )
    | SIGNED
    | UNSIGNED
    | FLOAT
    | DOUBLE
    | VOID
    | structSpecifier
    ;

structSpecifier
    : STRUCT IDENTIFIER (LBRACE structMemberDeclaration* RBRACE)?
    | STRUCT LBRACE structMemberDeclaration* RBRACE
    ;

structMemberDeclaration
    : typeSpecifier structDeclarator (COMMA structDeclarator)* SEMI
    ;

structDeclarator
    : pointer? IDENTIFIER arraySuffix?
    ;


/* =========================
   LEXER RULES
   ========================= */

INT      : 'int';
FLOAT    : 'float';
CHAR     : 'char';
VOID     : 'void';
DOUBLE   : 'double';
SIGNED   : 'signed';
UNSIGNED : 'unsigned';
SHORT    : 'short';
LONG     : 'long';

RETURN   : 'return';
IF       : 'if';
ELSE     : 'else';
WHILE    : 'while';
DO       : 'do';
FOR      : 'for';
BREAK    : 'break';
CONTINUE : 'continue';
SIZEOF   : 'sizeof';
NULL     : 'NULL';
SWITCH   : 'switch';
CASE     : 'case';
DEFAULT  : 'default';
STRUCT   : 'struct';

INC      : '++';
DEC      : '--';

LSHIFT_ASSIGN : '<<=';
RSHIFT_ASSIGN : '>>=';
ADD_ASSIGN    : '+=';
SUB_ASSIGN    : '-=';
MUL_ASSIGN    : '*=';
DIV_ASSIGN    : '/=';
MOD_ASSIGN    : '%=';
AND_ASSIGN    : '&=';
OR_ASSIGN     : '|=';
XOR_ASSIGN    : '^=';

LSHIFT   : '<<';
RSHIFT   : '>>';
EQ       : '==';
NEQ      : '!=';
LTE      : '<=';
GTE      : '>=';
AND      : '&&';
OR       : '||';

AMP      : '&';
PIPE     : '|';
CARET    : '^';
TILDE    : '~';

PLUS     : '+';
MINUS    : '-';
MUL      : '*';
DIV      : '/';
MOD      : '%';

LT       : '<';
GT       : '>';
NOT      : '!';

ASSIGN   : '=';

QUESTION : '?';
COLON    : ':';
COMMA    : ',';
SEMI     : ';';

LPAREN   : '(';
RPAREN   : ')';
LBRACE   : '{';
RBRACE   : '}';
LBRACK   : '[';
RBRACK   : ']';

ARROW    : '->';
DOT      : '.';

PREPROCESSOR_DIRECTIVE
    : '#' ~[\r\n]* -> channel(HIDDEN)
    ;

IDENTIFIER
    : [a-zA-Z_][a-zA-Z_0-9]*
    ;

INTEGER
    : [0-9]+
    ;

FLOAT_LITERAL
    : [0-9]+ '.' [0-9]+
    ;

CHAR_LITERAL
    : '\'' ( ~['\\\r\n] | '\\' [nrt'\\] ) '\''
    ;

STRING_LITERAL
    : '"' ( ~["\\\r\n] | '\\' . )* '"'
    ;

WS
    : [ \t\r\n]+ -> skip
    ;

LINE_COMMENT
    : '//' ~[\r\n]* -> skip
    ;

BLOCK_COMMENT
    : '/*' .*? '*/' -> skip
    ;

ERROR_CHAR
    : .
    ;
