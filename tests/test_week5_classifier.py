import pytest
from compiler.error_classifier import classify_error_message

def test_missing_semicolon_after_prototype_positive():
    c1 = classify_error_message("no viable alternative at input 'intadd(inta,intb)int'")
    assert c1.reason == "missing_semicolon_after_prototype"
    assert c1.fixable is True

    c2 = classify_error_message("mismatched input ')' expecting ';'")
    assert c2.reason == "missing_semicolon_after_prototype"
    assert c2.fixable is True

def test_missing_semicolon_after_prototype_negative():
    c1 = classify_error_message("no viable alternative at input 'if(x)y'")
    assert c1.reason != "missing_semicolon_after_prototype"

    c2 = classify_error_message("missing ';' at 'return'")
    assert c2.reason != "missing_semicolon_after_prototype"
    assert c2.reason == "missing_semicolon"

def test_missing_comma_params_positive():
    c1 = classify_error_message("no viable alternative at input 'intadd(intaint'")
    assert c1.reason == "missing_comma_params"
    assert c1.fixable is True

    c2 = classify_error_message("mismatched input 'int' expecting ')'")
    assert c2.reason == "missing_comma_params"
    assert c2.fixable is True

def test_missing_comma_params_negative():
    c1 = classify_error_message("extraneous input 'int' expecting identifier")
    assert c1.reason != "missing_comma_params"

    c2 = classify_error_message("no viable alternative at input 'x=y+z'")
    assert c2.reason != "missing_comma_params"

def test_missing_rparen_params_positive():
    c1 = classify_error_message("no viable alternative at input 'intadd(inta,intb;'")
    assert c1.reason == "missing_rparen_params"
    assert c1.fixable is True

    c2 = classify_error_message("no viable alternative at input 'intadd(inta,intb{'")
    assert c2.reason == "missing_rparen_params"
    assert c2.fixable is True

def test_missing_rparen_params_negative():
    c1 = classify_error_message("no viable alternative at input 'if(x<5{'")
    assert c1.reason != "missing_rparen_params"

    c2 = classify_error_message("no viable alternative at input 'while(i<10;'")
    assert c2.reason != "missing_rparen_params"

def test_missing_semicolon_after_global_positive():
    c1 = classify_error_message("missing ';' at 'int'")
    assert c1.reason == "missing_semicolon_after_global"
    assert c1.fixable is True

    c2 = classify_error_message("no viable alternative at input 'intcounterint'")
    assert c2.reason == "missing_semicolon_after_global"
    assert c2.fixable is True

def test_missing_semicolon_after_global_negative():
    c1 = classify_error_message("missing ';' at 'return'")
    assert c1.reason != "missing_semicolon_after_global"

    c2 = classify_error_message("missing ';' at '}'")
    assert c2.reason != "missing_semicolon_after_global"

def test_invalid_type_combination_positive():
    c1 = classify_error_message("no viable alternative at input 'longshort'")
    assert c1.reason == "invalid_type_combination"
    assert c1.fixable is False

    c2 = classify_error_message("no viable alternative at input 'unsignedfloat'")
    assert c2.reason == "invalid_type_combination"
    assert c2.fixable is False

def test_invalid_type_combination_negative():
    c1 = classify_error_message("no viable alternative at input 'printfloat'")
    assert c1.reason != "invalid_type_combination"

    c2 = classify_error_message("no viable alternative at input 'floatx'")
    assert c2.reason != "invalid_type_combination"
