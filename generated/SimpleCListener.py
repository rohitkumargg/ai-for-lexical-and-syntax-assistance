# Generated from grammar/SimpleC.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .SimpleCParser import SimpleCParser
else:
    from SimpleCParser import SimpleCParser

# This class defines a complete listener for a parse tree produced by SimpleCParser.
class SimpleCListener(ParseTreeListener):

    # Enter a parse tree produced by SimpleCParser#program.
    def enterProgram(self, ctx:SimpleCParser.ProgramContext):
        pass

    # Exit a parse tree produced by SimpleCParser#program.
    def exitProgram(self, ctx:SimpleCParser.ProgramContext):
        pass


    # Enter a parse tree produced by SimpleCParser#topLevelItem.
    def enterTopLevelItem(self, ctx:SimpleCParser.TopLevelItemContext):
        pass

    # Exit a parse tree produced by SimpleCParser#topLevelItem.
    def exitTopLevelItem(self, ctx:SimpleCParser.TopLevelItemContext):
        pass


    # Enter a parse tree produced by SimpleCParser#functionDeclaration.
    def enterFunctionDeclaration(self, ctx:SimpleCParser.FunctionDeclarationContext):
        pass

    # Exit a parse tree produced by SimpleCParser#functionDeclaration.
    def exitFunctionDeclaration(self, ctx:SimpleCParser.FunctionDeclarationContext):
        pass


    # Enter a parse tree produced by SimpleCParser#functionDef.
    def enterFunctionDef(self, ctx:SimpleCParser.FunctionDefContext):
        pass

    # Exit a parse tree produced by SimpleCParser#functionDef.
    def exitFunctionDef(self, ctx:SimpleCParser.FunctionDefContext):
        pass


    # Enter a parse tree produced by SimpleCParser#paramList.
    def enterParamList(self, ctx:SimpleCParser.ParamListContext):
        pass

    # Exit a parse tree produced by SimpleCParser#paramList.
    def exitParamList(self, ctx:SimpleCParser.ParamListContext):
        pass


    # Enter a parse tree produced by SimpleCParser#param.
    def enterParam(self, ctx:SimpleCParser.ParamContext):
        pass

    # Exit a parse tree produced by SimpleCParser#param.
    def exitParam(self, ctx:SimpleCParser.ParamContext):
        pass


    # Enter a parse tree produced by SimpleCParser#block.
    def enterBlock(self, ctx:SimpleCParser.BlockContext):
        pass

    # Exit a parse tree produced by SimpleCParser#block.
    def exitBlock(self, ctx:SimpleCParser.BlockContext):
        pass


    # Enter a parse tree produced by SimpleCParser#blockItem.
    def enterBlockItem(self, ctx:SimpleCParser.BlockItemContext):
        pass

    # Exit a parse tree produced by SimpleCParser#blockItem.
    def exitBlockItem(self, ctx:SimpleCParser.BlockItemContext):
        pass


    # Enter a parse tree produced by SimpleCParser#declaration.
    def enterDeclaration(self, ctx:SimpleCParser.DeclarationContext):
        pass

    # Exit a parse tree produced by SimpleCParser#declaration.
    def exitDeclaration(self, ctx:SimpleCParser.DeclarationContext):
        pass


    # Enter a parse tree produced by SimpleCParser#declarationNoSemi.
    def enterDeclarationNoSemi(self, ctx:SimpleCParser.DeclarationNoSemiContext):
        pass

    # Exit a parse tree produced by SimpleCParser#declarationNoSemi.
    def exitDeclarationNoSemi(self, ctx:SimpleCParser.DeclarationNoSemiContext):
        pass


    # Enter a parse tree produced by SimpleCParser#initDeclaratorList.
    def enterInitDeclaratorList(self, ctx:SimpleCParser.InitDeclaratorListContext):
        pass

    # Exit a parse tree produced by SimpleCParser#initDeclaratorList.
    def exitInitDeclaratorList(self, ctx:SimpleCParser.InitDeclaratorListContext):
        pass


    # Enter a parse tree produced by SimpleCParser#initDeclarator.
    def enterInitDeclarator(self, ctx:SimpleCParser.InitDeclaratorContext):
        pass

    # Exit a parse tree produced by SimpleCParser#initDeclarator.
    def exitInitDeclarator(self, ctx:SimpleCParser.InitDeclaratorContext):
        pass


    # Enter a parse tree produced by SimpleCParser#initializer.
    def enterInitializer(self, ctx:SimpleCParser.InitializerContext):
        pass

    # Exit a parse tree produced by SimpleCParser#initializer.
    def exitInitializer(self, ctx:SimpleCParser.InitializerContext):
        pass


    # Enter a parse tree produced by SimpleCParser#pointer.
    def enterPointer(self, ctx:SimpleCParser.PointerContext):
        pass

    # Exit a parse tree produced by SimpleCParser#pointer.
    def exitPointer(self, ctx:SimpleCParser.PointerContext):
        pass


    # Enter a parse tree produced by SimpleCParser#arraySuffix.
    def enterArraySuffix(self, ctx:SimpleCParser.ArraySuffixContext):
        pass

    # Exit a parse tree produced by SimpleCParser#arraySuffix.
    def exitArraySuffix(self, ctx:SimpleCParser.ArraySuffixContext):
        pass


    # Enter a parse tree produced by SimpleCParser#statement.
    def enterStatement(self, ctx:SimpleCParser.StatementContext):
        pass

    # Exit a parse tree produced by SimpleCParser#statement.
    def exitStatement(self, ctx:SimpleCParser.StatementContext):
        pass


    # Enter a parse tree produced by SimpleCParser#switchStatement.
    def enterSwitchStatement(self, ctx:SimpleCParser.SwitchStatementContext):
        pass

    # Exit a parse tree produced by SimpleCParser#switchStatement.
    def exitSwitchStatement(self, ctx:SimpleCParser.SwitchStatementContext):
        pass


    # Enter a parse tree produced by SimpleCParser#labeledStatement.
    def enterLabeledStatement(self, ctx:SimpleCParser.LabeledStatementContext):
        pass

    # Exit a parse tree produced by SimpleCParser#labeledStatement.
    def exitLabeledStatement(self, ctx:SimpleCParser.LabeledStatementContext):
        pass


    # Enter a parse tree produced by SimpleCParser#emptyStatement.
    def enterEmptyStatement(self, ctx:SimpleCParser.EmptyStatementContext):
        pass

    # Exit a parse tree produced by SimpleCParser#emptyStatement.
    def exitEmptyStatement(self, ctx:SimpleCParser.EmptyStatementContext):
        pass


    # Enter a parse tree produced by SimpleCParser#exprStatement.
    def enterExprStatement(self, ctx:SimpleCParser.ExprStatementContext):
        pass

    # Exit a parse tree produced by SimpleCParser#exprStatement.
    def exitExprStatement(self, ctx:SimpleCParser.ExprStatementContext):
        pass


    # Enter a parse tree produced by SimpleCParser#ifStatement.
    def enterIfStatement(self, ctx:SimpleCParser.IfStatementContext):
        pass

    # Exit a parse tree produced by SimpleCParser#ifStatement.
    def exitIfStatement(self, ctx:SimpleCParser.IfStatementContext):
        pass


    # Enter a parse tree produced by SimpleCParser#whileStatement.
    def enterWhileStatement(self, ctx:SimpleCParser.WhileStatementContext):
        pass

    # Exit a parse tree produced by SimpleCParser#whileStatement.
    def exitWhileStatement(self, ctx:SimpleCParser.WhileStatementContext):
        pass


    # Enter a parse tree produced by SimpleCParser#doWhileStatement.
    def enterDoWhileStatement(self, ctx:SimpleCParser.DoWhileStatementContext):
        pass

    # Exit a parse tree produced by SimpleCParser#doWhileStatement.
    def exitDoWhileStatement(self, ctx:SimpleCParser.DoWhileStatementContext):
        pass


    # Enter a parse tree produced by SimpleCParser#forStatement.
    def enterForStatement(self, ctx:SimpleCParser.ForStatementContext):
        pass

    # Exit a parse tree produced by SimpleCParser#forStatement.
    def exitForStatement(self, ctx:SimpleCParser.ForStatementContext):
        pass


    # Enter a parse tree produced by SimpleCParser#forInit.
    def enterForInit(self, ctx:SimpleCParser.ForInitContext):
        pass

    # Exit a parse tree produced by SimpleCParser#forInit.
    def exitForInit(self, ctx:SimpleCParser.ForInitContext):
        pass


    # Enter a parse tree produced by SimpleCParser#returnStatement.
    def enterReturnStatement(self, ctx:SimpleCParser.ReturnStatementContext):
        pass

    # Exit a parse tree produced by SimpleCParser#returnStatement.
    def exitReturnStatement(self, ctx:SimpleCParser.ReturnStatementContext):
        pass


    # Enter a parse tree produced by SimpleCParser#breakStatement.
    def enterBreakStatement(self, ctx:SimpleCParser.BreakStatementContext):
        pass

    # Exit a parse tree produced by SimpleCParser#breakStatement.
    def exitBreakStatement(self, ctx:SimpleCParser.BreakStatementContext):
        pass


    # Enter a parse tree produced by SimpleCParser#continueStatement.
    def enterContinueStatement(self, ctx:SimpleCParser.ContinueStatementContext):
        pass

    # Exit a parse tree produced by SimpleCParser#continueStatement.
    def exitContinueStatement(self, ctx:SimpleCParser.ContinueStatementContext):
        pass


    # Enter a parse tree produced by SimpleCParser#expression.
    def enterExpression(self, ctx:SimpleCParser.ExpressionContext):
        pass

    # Exit a parse tree produced by SimpleCParser#expression.
    def exitExpression(self, ctx:SimpleCParser.ExpressionContext):
        pass


    # Enter a parse tree produced by SimpleCParser#assignmentExpression.
    def enterAssignmentExpression(self, ctx:SimpleCParser.AssignmentExpressionContext):
        pass

    # Exit a parse tree produced by SimpleCParser#assignmentExpression.
    def exitAssignmentExpression(self, ctx:SimpleCParser.AssignmentExpressionContext):
        pass


    # Enter a parse tree produced by SimpleCParser#assignmentOperator.
    def enterAssignmentOperator(self, ctx:SimpleCParser.AssignmentOperatorContext):
        pass

    # Exit a parse tree produced by SimpleCParser#assignmentOperator.
    def exitAssignmentOperator(self, ctx:SimpleCParser.AssignmentOperatorContext):
        pass


    # Enter a parse tree produced by SimpleCParser#conditionalExpression.
    def enterConditionalExpression(self, ctx:SimpleCParser.ConditionalExpressionContext):
        pass

    # Exit a parse tree produced by SimpleCParser#conditionalExpression.
    def exitConditionalExpression(self, ctx:SimpleCParser.ConditionalExpressionContext):
        pass


    # Enter a parse tree produced by SimpleCParser#logicalOrExpression.
    def enterLogicalOrExpression(self, ctx:SimpleCParser.LogicalOrExpressionContext):
        pass

    # Exit a parse tree produced by SimpleCParser#logicalOrExpression.
    def exitLogicalOrExpression(self, ctx:SimpleCParser.LogicalOrExpressionContext):
        pass


    # Enter a parse tree produced by SimpleCParser#logicalAndExpression.
    def enterLogicalAndExpression(self, ctx:SimpleCParser.LogicalAndExpressionContext):
        pass

    # Exit a parse tree produced by SimpleCParser#logicalAndExpression.
    def exitLogicalAndExpression(self, ctx:SimpleCParser.LogicalAndExpressionContext):
        pass


    # Enter a parse tree produced by SimpleCParser#inclusiveOrExpression.
    def enterInclusiveOrExpression(self, ctx:SimpleCParser.InclusiveOrExpressionContext):
        pass

    # Exit a parse tree produced by SimpleCParser#inclusiveOrExpression.
    def exitInclusiveOrExpression(self, ctx:SimpleCParser.InclusiveOrExpressionContext):
        pass


    # Enter a parse tree produced by SimpleCParser#exclusiveOrExpression.
    def enterExclusiveOrExpression(self, ctx:SimpleCParser.ExclusiveOrExpressionContext):
        pass

    # Exit a parse tree produced by SimpleCParser#exclusiveOrExpression.
    def exitExclusiveOrExpression(self, ctx:SimpleCParser.ExclusiveOrExpressionContext):
        pass


    # Enter a parse tree produced by SimpleCParser#andExpression.
    def enterAndExpression(self, ctx:SimpleCParser.AndExpressionContext):
        pass

    # Exit a parse tree produced by SimpleCParser#andExpression.
    def exitAndExpression(self, ctx:SimpleCParser.AndExpressionContext):
        pass


    # Enter a parse tree produced by SimpleCParser#equalityExpression.
    def enterEqualityExpression(self, ctx:SimpleCParser.EqualityExpressionContext):
        pass

    # Exit a parse tree produced by SimpleCParser#equalityExpression.
    def exitEqualityExpression(self, ctx:SimpleCParser.EqualityExpressionContext):
        pass


    # Enter a parse tree produced by SimpleCParser#relationalExpression.
    def enterRelationalExpression(self, ctx:SimpleCParser.RelationalExpressionContext):
        pass

    # Exit a parse tree produced by SimpleCParser#relationalExpression.
    def exitRelationalExpression(self, ctx:SimpleCParser.RelationalExpressionContext):
        pass


    # Enter a parse tree produced by SimpleCParser#shiftExpression.
    def enterShiftExpression(self, ctx:SimpleCParser.ShiftExpressionContext):
        pass

    # Exit a parse tree produced by SimpleCParser#shiftExpression.
    def exitShiftExpression(self, ctx:SimpleCParser.ShiftExpressionContext):
        pass


    # Enter a parse tree produced by SimpleCParser#additiveExpression.
    def enterAdditiveExpression(self, ctx:SimpleCParser.AdditiveExpressionContext):
        pass

    # Exit a parse tree produced by SimpleCParser#additiveExpression.
    def exitAdditiveExpression(self, ctx:SimpleCParser.AdditiveExpressionContext):
        pass


    # Enter a parse tree produced by SimpleCParser#multiplicativeExpression.
    def enterMultiplicativeExpression(self, ctx:SimpleCParser.MultiplicativeExpressionContext):
        pass

    # Exit a parse tree produced by SimpleCParser#multiplicativeExpression.
    def exitMultiplicativeExpression(self, ctx:SimpleCParser.MultiplicativeExpressionContext):
        pass


    # Enter a parse tree produced by SimpleCParser#unaryExpression.
    def enterUnaryExpression(self, ctx:SimpleCParser.UnaryExpressionContext):
        pass

    # Exit a parse tree produced by SimpleCParser#unaryExpression.
    def exitUnaryExpression(self, ctx:SimpleCParser.UnaryExpressionContext):
        pass


    # Enter a parse tree produced by SimpleCParser#postfixExpression.
    def enterPostfixExpression(self, ctx:SimpleCParser.PostfixExpressionContext):
        pass

    # Exit a parse tree produced by SimpleCParser#postfixExpression.
    def exitPostfixExpression(self, ctx:SimpleCParser.PostfixExpressionContext):
        pass


    # Enter a parse tree produced by SimpleCParser#postfixPart.
    def enterPostfixPart(self, ctx:SimpleCParser.PostfixPartContext):
        pass

    # Exit a parse tree produced by SimpleCParser#postfixPart.
    def exitPostfixPart(self, ctx:SimpleCParser.PostfixPartContext):
        pass


    # Enter a parse tree produced by SimpleCParser#argumentList.
    def enterArgumentList(self, ctx:SimpleCParser.ArgumentListContext):
        pass

    # Exit a parse tree produced by SimpleCParser#argumentList.
    def exitArgumentList(self, ctx:SimpleCParser.ArgumentListContext):
        pass


    # Enter a parse tree produced by SimpleCParser#primaryExpression.
    def enterPrimaryExpression(self, ctx:SimpleCParser.PrimaryExpressionContext):
        pass

    # Exit a parse tree produced by SimpleCParser#primaryExpression.
    def exitPrimaryExpression(self, ctx:SimpleCParser.PrimaryExpressionContext):
        pass


    # Enter a parse tree produced by SimpleCParser#typeSpecifier.
    def enterTypeSpecifier(self, ctx:SimpleCParser.TypeSpecifierContext):
        pass

    # Exit a parse tree produced by SimpleCParser#typeSpecifier.
    def exitTypeSpecifier(self, ctx:SimpleCParser.TypeSpecifierContext):
        pass


    # Enter a parse tree produced by SimpleCParser#structSpecifier.
    def enterStructSpecifier(self, ctx:SimpleCParser.StructSpecifierContext):
        pass

    # Exit a parse tree produced by SimpleCParser#structSpecifier.
    def exitStructSpecifier(self, ctx:SimpleCParser.StructSpecifierContext):
        pass


    # Enter a parse tree produced by SimpleCParser#structMemberDeclaration.
    def enterStructMemberDeclaration(self, ctx:SimpleCParser.StructMemberDeclarationContext):
        pass

    # Exit a parse tree produced by SimpleCParser#structMemberDeclaration.
    def exitStructMemberDeclaration(self, ctx:SimpleCParser.StructMemberDeclarationContext):
        pass


    # Enter a parse tree produced by SimpleCParser#structDeclarator.
    def enterStructDeclarator(self, ctx:SimpleCParser.StructDeclaratorContext):
        pass

    # Exit a parse tree produced by SimpleCParser#structDeclarator.
    def exitStructDeclarator(self, ctx:SimpleCParser.StructDeclaratorContext):
        pass



del SimpleCParser