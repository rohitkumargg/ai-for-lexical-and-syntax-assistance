# Generated from grammar/SimpleC.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .SimpleCParser import SimpleCParser
else:
    from SimpleCParser import SimpleCParser

# This class defines a complete generic visitor for a parse tree produced by SimpleCParser.

class SimpleCVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by SimpleCParser#program.
    def visitProgram(self, ctx:SimpleCParser.ProgramContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#topLevelItem.
    def visitTopLevelItem(self, ctx:SimpleCParser.TopLevelItemContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#functionDeclaration.
    def visitFunctionDeclaration(self, ctx:SimpleCParser.FunctionDeclarationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#functionDef.
    def visitFunctionDef(self, ctx:SimpleCParser.FunctionDefContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#paramList.
    def visitParamList(self, ctx:SimpleCParser.ParamListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#param.
    def visitParam(self, ctx:SimpleCParser.ParamContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#block.
    def visitBlock(self, ctx:SimpleCParser.BlockContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#blockItem.
    def visitBlockItem(self, ctx:SimpleCParser.BlockItemContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#declaration.
    def visitDeclaration(self, ctx:SimpleCParser.DeclarationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#declarationNoSemi.
    def visitDeclarationNoSemi(self, ctx:SimpleCParser.DeclarationNoSemiContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#initDeclaratorList.
    def visitInitDeclaratorList(self, ctx:SimpleCParser.InitDeclaratorListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#initDeclarator.
    def visitInitDeclarator(self, ctx:SimpleCParser.InitDeclaratorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#initializer.
    def visitInitializer(self, ctx:SimpleCParser.InitializerContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#pointer.
    def visitPointer(self, ctx:SimpleCParser.PointerContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#arraySuffix.
    def visitArraySuffix(self, ctx:SimpleCParser.ArraySuffixContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#statement.
    def visitStatement(self, ctx:SimpleCParser.StatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#switchStatement.
    def visitSwitchStatement(self, ctx:SimpleCParser.SwitchStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#labeledStatement.
    def visitLabeledStatement(self, ctx:SimpleCParser.LabeledStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#emptyStatement.
    def visitEmptyStatement(self, ctx:SimpleCParser.EmptyStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#exprStatement.
    def visitExprStatement(self, ctx:SimpleCParser.ExprStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#ifStatement.
    def visitIfStatement(self, ctx:SimpleCParser.IfStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#whileStatement.
    def visitWhileStatement(self, ctx:SimpleCParser.WhileStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#doWhileStatement.
    def visitDoWhileStatement(self, ctx:SimpleCParser.DoWhileStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#forStatement.
    def visitForStatement(self, ctx:SimpleCParser.ForStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#forInit.
    def visitForInit(self, ctx:SimpleCParser.ForInitContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#returnStatement.
    def visitReturnStatement(self, ctx:SimpleCParser.ReturnStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#breakStatement.
    def visitBreakStatement(self, ctx:SimpleCParser.BreakStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#continueStatement.
    def visitContinueStatement(self, ctx:SimpleCParser.ContinueStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#expression.
    def visitExpression(self, ctx:SimpleCParser.ExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#assignmentExpression.
    def visitAssignmentExpression(self, ctx:SimpleCParser.AssignmentExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#assignmentOperator.
    def visitAssignmentOperator(self, ctx:SimpleCParser.AssignmentOperatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#conditionalExpression.
    def visitConditionalExpression(self, ctx:SimpleCParser.ConditionalExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#logicalOrExpression.
    def visitLogicalOrExpression(self, ctx:SimpleCParser.LogicalOrExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#logicalAndExpression.
    def visitLogicalAndExpression(self, ctx:SimpleCParser.LogicalAndExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#inclusiveOrExpression.
    def visitInclusiveOrExpression(self, ctx:SimpleCParser.InclusiveOrExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#exclusiveOrExpression.
    def visitExclusiveOrExpression(self, ctx:SimpleCParser.ExclusiveOrExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#andExpression.
    def visitAndExpression(self, ctx:SimpleCParser.AndExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#equalityExpression.
    def visitEqualityExpression(self, ctx:SimpleCParser.EqualityExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#relationalExpression.
    def visitRelationalExpression(self, ctx:SimpleCParser.RelationalExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#shiftExpression.
    def visitShiftExpression(self, ctx:SimpleCParser.ShiftExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#additiveExpression.
    def visitAdditiveExpression(self, ctx:SimpleCParser.AdditiveExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#multiplicativeExpression.
    def visitMultiplicativeExpression(self, ctx:SimpleCParser.MultiplicativeExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#unaryExpression.
    def visitUnaryExpression(self, ctx:SimpleCParser.UnaryExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#postfixExpression.
    def visitPostfixExpression(self, ctx:SimpleCParser.PostfixExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#postfixPart.
    def visitPostfixPart(self, ctx:SimpleCParser.PostfixPartContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#argumentList.
    def visitArgumentList(self, ctx:SimpleCParser.ArgumentListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#primaryExpression.
    def visitPrimaryExpression(self, ctx:SimpleCParser.PrimaryExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#typeSpecifier.
    def visitTypeSpecifier(self, ctx:SimpleCParser.TypeSpecifierContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#structSpecifier.
    def visitStructSpecifier(self, ctx:SimpleCParser.StructSpecifierContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#structMemberDeclaration.
    def visitStructMemberDeclaration(self, ctx:SimpleCParser.StructMemberDeclarationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SimpleCParser#structDeclarator.
    def visitStructDeclarator(self, ctx:SimpleCParser.StructDeclaratorContext):
        return self.visitChildren(ctx)



del SimpleCParser