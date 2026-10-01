# Generated from grammar/SimpleC.g4 by ANTLR 4.13.2
# encoding: utf-8
from antlr4 import *
from io import StringIO
import sys
if sys.version_info[1] > 5:
	from typing import TextIO
else:
	from typing.io import TextIO

def serializedATN():
    return [
        4,1,78,560,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,2,6,7,
        6,2,7,7,7,2,8,7,8,2,9,7,9,2,10,7,10,2,11,7,11,2,12,7,12,2,13,7,13,
        2,14,7,14,2,15,7,15,2,16,7,16,2,17,7,17,2,18,7,18,2,19,7,19,2,20,
        7,20,2,21,7,21,2,22,7,22,2,23,7,23,2,24,7,24,2,25,7,25,2,26,7,26,
        2,27,7,27,2,28,7,28,2,29,7,29,2,30,7,30,2,31,7,31,2,32,7,32,2,33,
        7,33,2,34,7,34,2,35,7,35,2,36,7,36,2,37,7,37,2,38,7,38,2,39,7,39,
        2,40,7,40,2,41,7,41,2,42,7,42,2,43,7,43,2,44,7,44,2,45,7,45,2,46,
        7,46,2,47,7,47,2,48,7,48,2,49,7,49,2,50,7,50,1,0,4,0,104,8,0,11,
        0,12,0,105,1,0,1,0,1,1,1,1,1,1,3,1,113,8,1,1,2,1,2,3,2,117,8,2,1,
        2,1,2,1,2,3,2,122,8,2,1,2,1,2,1,2,1,3,1,3,3,3,129,8,3,1,3,1,3,1,
        3,3,3,134,8,3,1,3,1,3,1,3,1,4,1,4,1,4,5,4,142,8,4,10,4,12,4,145,
        9,4,1,5,1,5,3,5,149,8,5,1,5,3,5,152,8,5,1,5,3,5,155,8,5,1,6,1,6,
        5,6,159,8,6,10,6,12,6,162,9,6,1,6,1,6,1,7,1,7,3,7,168,8,7,1,8,1,
        8,1,8,1,9,1,9,3,9,175,8,9,1,10,1,10,1,10,5,10,180,8,10,10,10,12,
        10,183,9,10,1,11,3,11,186,8,11,1,11,1,11,3,11,190,8,11,1,11,1,11,
        3,11,194,8,11,1,12,1,12,1,12,1,12,1,12,5,12,201,8,12,10,12,12,12,
        204,9,12,1,12,3,12,207,8,12,3,12,209,8,12,1,12,3,12,212,8,12,1,13,
        4,13,215,8,13,11,13,12,13,216,1,14,1,14,3,14,221,8,14,1,14,4,14,
        224,8,14,11,14,12,14,225,1,15,1,15,1,15,1,15,1,15,1,15,1,15,1,15,
        1,15,1,15,1,15,1,15,3,15,240,8,15,1,16,1,16,1,16,1,16,1,16,1,16,
        1,17,1,17,1,17,1,17,1,17,1,17,3,17,254,8,17,1,18,1,18,1,19,3,19,
        259,8,19,1,19,1,19,1,20,1,20,1,20,1,20,1,20,1,20,1,20,3,20,270,8,
        20,1,21,1,21,1,21,1,21,1,21,1,21,1,22,1,22,1,22,1,22,1,22,1,22,1,
        22,1,22,1,23,1,23,1,23,3,23,289,8,23,1,23,1,23,3,23,293,8,23,1,23,
        1,23,3,23,297,8,23,1,23,1,23,1,23,1,24,1,24,3,24,304,8,24,1,25,1,
        25,3,25,308,8,25,1,25,1,25,1,26,1,26,1,26,1,27,1,27,1,27,1,28,1,
        28,1,28,5,28,321,8,28,10,28,12,28,324,9,28,1,29,1,29,1,29,1,29,1,
        29,3,29,331,8,29,1,30,1,30,1,31,1,31,1,31,1,31,1,31,1,31,3,31,341,
        8,31,1,32,1,32,1,32,5,32,346,8,32,10,32,12,32,349,9,32,1,33,1,33,
        1,33,5,33,354,8,33,10,33,12,33,357,9,33,1,34,1,34,1,34,5,34,362,
        8,34,10,34,12,34,365,9,34,1,35,1,35,1,35,5,35,370,8,35,10,35,12,
        35,373,9,35,1,36,1,36,1,36,5,36,378,8,36,10,36,12,36,381,9,36,1,
        37,1,37,1,37,5,37,386,8,37,10,37,12,37,389,9,37,1,38,1,38,1,38,5,
        38,394,8,38,10,38,12,38,397,9,38,1,39,1,39,1,39,5,39,402,8,39,10,
        39,12,39,405,9,39,1,40,1,40,1,40,5,40,410,8,40,10,40,12,40,413,9,
        40,1,41,1,41,1,41,5,41,418,8,41,10,41,12,41,421,9,41,1,42,1,42,1,
        42,1,42,1,42,1,42,3,42,429,8,42,1,42,1,42,1,42,1,42,1,42,1,42,1,
        42,3,42,438,8,42,1,42,1,42,1,42,3,42,443,8,42,3,42,445,8,42,1,43,
        1,43,5,43,449,8,43,10,43,12,43,452,9,43,1,44,1,44,1,44,1,44,1,44,
        1,44,3,44,460,8,44,1,44,1,44,1,44,1,44,1,44,1,44,1,44,3,44,469,8,
        44,1,45,1,45,1,45,5,45,474,8,45,10,45,12,45,477,9,45,1,46,1,46,1,
        46,1,46,1,46,1,46,1,46,1,46,1,46,1,46,3,46,489,8,46,1,47,3,47,492,
        8,47,1,47,1,47,1,47,3,47,497,8,47,1,47,1,47,1,47,3,47,502,8,47,1,
        47,1,47,3,47,506,8,47,1,47,3,47,509,8,47,1,47,1,47,1,47,1,47,1,47,
        1,47,3,47,517,8,47,1,48,1,48,1,48,1,48,5,48,523,8,48,10,48,12,48,
        526,9,48,1,48,3,48,529,8,48,1,48,1,48,1,48,5,48,534,8,48,10,48,12,
        48,537,9,48,1,48,3,48,540,8,48,1,49,1,49,1,49,1,49,5,49,546,8,49,
        10,49,12,49,549,9,49,1,49,1,49,1,50,3,50,554,8,50,1,50,1,50,3,50,
        558,8,50,1,50,0,0,51,0,2,4,6,8,10,12,14,16,18,20,22,24,26,28,30,
        32,34,36,38,40,42,44,46,48,50,52,54,56,58,60,62,64,66,68,70,72,74,
        76,78,80,82,84,86,88,90,92,94,96,98,100,0,8,2,0,26,35,56,56,1,0,
        38,39,2,0,40,41,53,54,1,0,36,37,1,0,48,49,1,0,50,52,4,0,24,25,44,
        44,47,50,55,55,1,0,6,7,606,0,103,1,0,0,0,2,112,1,0,0,0,4,114,1,0,
        0,0,6,126,1,0,0,0,8,138,1,0,0,0,10,146,1,0,0,0,12,156,1,0,0,0,14,
        167,1,0,0,0,16,169,1,0,0,0,18,172,1,0,0,0,20,176,1,0,0,0,22,185,
        1,0,0,0,24,211,1,0,0,0,26,214,1,0,0,0,28,223,1,0,0,0,30,239,1,0,
        0,0,32,241,1,0,0,0,34,253,1,0,0,0,36,255,1,0,0,0,38,258,1,0,0,0,
        40,262,1,0,0,0,42,271,1,0,0,0,44,277,1,0,0,0,46,285,1,0,0,0,48,303,
        1,0,0,0,50,305,1,0,0,0,52,311,1,0,0,0,54,314,1,0,0,0,56,317,1,0,
        0,0,58,330,1,0,0,0,60,332,1,0,0,0,62,334,1,0,0,0,64,342,1,0,0,0,
        66,350,1,0,0,0,68,358,1,0,0,0,70,366,1,0,0,0,72,374,1,0,0,0,74,382,
        1,0,0,0,76,390,1,0,0,0,78,398,1,0,0,0,80,406,1,0,0,0,82,414,1,0,
        0,0,84,444,1,0,0,0,86,446,1,0,0,0,88,468,1,0,0,0,90,470,1,0,0,0,
        92,488,1,0,0,0,94,516,1,0,0,0,96,539,1,0,0,0,98,541,1,0,0,0,100,
        553,1,0,0,0,102,104,3,2,1,0,103,102,1,0,0,0,104,105,1,0,0,0,105,
        103,1,0,0,0,105,106,1,0,0,0,106,107,1,0,0,0,107,108,5,0,0,1,108,
        1,1,0,0,0,109,113,3,6,3,0,110,113,3,4,2,0,111,113,3,16,8,0,112,109,
        1,0,0,0,112,110,1,0,0,0,112,111,1,0,0,0,113,3,1,0,0,0,114,116,3,
        94,47,0,115,117,3,26,13,0,116,115,1,0,0,0,116,117,1,0,0,0,117,118,
        1,0,0,0,118,119,5,70,0,0,119,121,5,61,0,0,120,122,3,8,4,0,121,120,
        1,0,0,0,121,122,1,0,0,0,122,123,1,0,0,0,123,124,5,62,0,0,124,125,
        5,60,0,0,125,5,1,0,0,0,126,128,3,94,47,0,127,129,3,26,13,0,128,127,
        1,0,0,0,128,129,1,0,0,0,129,130,1,0,0,0,130,131,5,70,0,0,131,133,
        5,61,0,0,132,134,3,8,4,0,133,132,1,0,0,0,133,134,1,0,0,0,134,135,
        1,0,0,0,135,136,5,62,0,0,136,137,3,12,6,0,137,7,1,0,0,0,138,143,
        3,10,5,0,139,140,5,59,0,0,140,142,3,10,5,0,141,139,1,0,0,0,142,145,
        1,0,0,0,143,141,1,0,0,0,143,144,1,0,0,0,144,9,1,0,0,0,145,143,1,
        0,0,0,146,148,3,94,47,0,147,149,3,26,13,0,148,147,1,0,0,0,148,149,
        1,0,0,0,149,151,1,0,0,0,150,152,5,70,0,0,151,150,1,0,0,0,151,152,
        1,0,0,0,152,154,1,0,0,0,153,155,3,28,14,0,154,153,1,0,0,0,154,155,
        1,0,0,0,155,11,1,0,0,0,156,160,5,63,0,0,157,159,3,14,7,0,158,157,
        1,0,0,0,159,162,1,0,0,0,160,158,1,0,0,0,160,161,1,0,0,0,161,163,
        1,0,0,0,162,160,1,0,0,0,163,164,5,64,0,0,164,13,1,0,0,0,165,168,
        3,16,8,0,166,168,3,30,15,0,167,165,1,0,0,0,167,166,1,0,0,0,168,15,
        1,0,0,0,169,170,3,18,9,0,170,171,5,60,0,0,171,17,1,0,0,0,172,174,
        3,94,47,0,173,175,3,20,10,0,174,173,1,0,0,0,174,175,1,0,0,0,175,
        19,1,0,0,0,176,181,3,22,11,0,177,178,5,59,0,0,178,180,3,22,11,0,
        179,177,1,0,0,0,180,183,1,0,0,0,181,179,1,0,0,0,181,182,1,0,0,0,
        182,21,1,0,0,0,183,181,1,0,0,0,184,186,3,26,13,0,185,184,1,0,0,0,
        185,186,1,0,0,0,186,187,1,0,0,0,187,189,5,70,0,0,188,190,3,28,14,
        0,189,188,1,0,0,0,189,190,1,0,0,0,190,193,1,0,0,0,191,192,5,56,0,
        0,192,194,3,24,12,0,193,191,1,0,0,0,193,194,1,0,0,0,194,23,1,0,0,
        0,195,212,3,58,29,0,196,208,5,63,0,0,197,202,3,24,12,0,198,199,5,
        59,0,0,199,201,3,24,12,0,200,198,1,0,0,0,201,204,1,0,0,0,202,200,
        1,0,0,0,202,203,1,0,0,0,203,206,1,0,0,0,204,202,1,0,0,0,205,207,
        5,59,0,0,206,205,1,0,0,0,206,207,1,0,0,0,207,209,1,0,0,0,208,197,
        1,0,0,0,208,209,1,0,0,0,209,210,1,0,0,0,210,212,5,64,0,0,211,195,
        1,0,0,0,211,196,1,0,0,0,212,25,1,0,0,0,213,215,5,50,0,0,214,213,
        1,0,0,0,215,216,1,0,0,0,216,214,1,0,0,0,216,217,1,0,0,0,217,27,1,
        0,0,0,218,220,5,65,0,0,219,221,3,56,28,0,220,219,1,0,0,0,220,221,
        1,0,0,0,221,222,1,0,0,0,222,224,5,66,0,0,223,218,1,0,0,0,224,225,
        1,0,0,0,225,223,1,0,0,0,225,226,1,0,0,0,226,29,1,0,0,0,227,240,3,
        36,18,0,228,240,3,38,19,0,229,240,3,40,20,0,230,240,3,42,21,0,231,
        240,3,44,22,0,232,240,3,46,23,0,233,240,3,32,16,0,234,240,3,34,17,
        0,235,240,3,50,25,0,236,240,3,52,26,0,237,240,3,54,27,0,238,240,
        3,12,6,0,239,227,1,0,0,0,239,228,1,0,0,0,239,229,1,0,0,0,239,230,
        1,0,0,0,239,231,1,0,0,0,239,232,1,0,0,0,239,233,1,0,0,0,239,234,
        1,0,0,0,239,235,1,0,0,0,239,236,1,0,0,0,239,237,1,0,0,0,239,238,
        1,0,0,0,240,31,1,0,0,0,241,242,5,20,0,0,242,243,5,61,0,0,243,244,
        3,56,28,0,244,245,5,62,0,0,245,246,3,30,15,0,246,33,1,0,0,0,247,
        248,5,21,0,0,248,249,3,62,31,0,249,250,5,58,0,0,250,254,1,0,0,0,
        251,252,5,22,0,0,252,254,5,58,0,0,253,247,1,0,0,0,253,251,1,0,0,
        0,254,35,1,0,0,0,255,256,5,60,0,0,256,37,1,0,0,0,257,259,3,56,28,
        0,258,257,1,0,0,0,258,259,1,0,0,0,259,260,1,0,0,0,260,261,5,60,0,
        0,261,39,1,0,0,0,262,263,5,11,0,0,263,264,5,61,0,0,264,265,3,56,
        28,0,265,266,5,62,0,0,266,269,3,30,15,0,267,268,5,12,0,0,268,270,
        3,30,15,0,269,267,1,0,0,0,269,270,1,0,0,0,270,41,1,0,0,0,271,272,
        5,13,0,0,272,273,5,61,0,0,273,274,3,56,28,0,274,275,5,62,0,0,275,
        276,3,30,15,0,276,43,1,0,0,0,277,278,5,14,0,0,278,279,3,30,15,0,
        279,280,5,13,0,0,280,281,5,61,0,0,281,282,3,56,28,0,282,283,5,62,
        0,0,283,284,5,60,0,0,284,45,1,0,0,0,285,286,5,15,0,0,286,288,5,61,
        0,0,287,289,3,48,24,0,288,287,1,0,0,0,288,289,1,0,0,0,289,290,1,
        0,0,0,290,292,5,60,0,0,291,293,3,56,28,0,292,291,1,0,0,0,292,293,
        1,0,0,0,293,294,1,0,0,0,294,296,5,60,0,0,295,297,3,56,28,0,296,295,
        1,0,0,0,296,297,1,0,0,0,297,298,1,0,0,0,298,299,5,62,0,0,299,300,
        3,30,15,0,300,47,1,0,0,0,301,304,3,18,9,0,302,304,3,56,28,0,303,
        301,1,0,0,0,303,302,1,0,0,0,304,49,1,0,0,0,305,307,5,10,0,0,306,
        308,3,56,28,0,307,306,1,0,0,0,307,308,1,0,0,0,308,309,1,0,0,0,309,
        310,5,60,0,0,310,51,1,0,0,0,311,312,5,16,0,0,312,313,5,60,0,0,313,
        53,1,0,0,0,314,315,5,17,0,0,315,316,5,60,0,0,316,55,1,0,0,0,317,
        322,3,58,29,0,318,319,5,59,0,0,319,321,3,58,29,0,320,318,1,0,0,0,
        321,324,1,0,0,0,322,320,1,0,0,0,322,323,1,0,0,0,323,57,1,0,0,0,324,
        322,1,0,0,0,325,331,3,62,31,0,326,327,3,84,42,0,327,328,3,60,30,
        0,328,329,3,58,29,0,329,331,1,0,0,0,330,325,1,0,0,0,330,326,1,0,
        0,0,331,59,1,0,0,0,332,333,7,0,0,0,333,61,1,0,0,0,334,340,3,64,32,
        0,335,336,5,57,0,0,336,337,3,56,28,0,337,338,5,58,0,0,338,339,3,
        62,31,0,339,341,1,0,0,0,340,335,1,0,0,0,340,341,1,0,0,0,341,63,1,
        0,0,0,342,347,3,66,33,0,343,344,5,43,0,0,344,346,3,66,33,0,345,343,
        1,0,0,0,346,349,1,0,0,0,347,345,1,0,0,0,347,348,1,0,0,0,348,65,1,
        0,0,0,349,347,1,0,0,0,350,355,3,68,34,0,351,352,5,42,0,0,352,354,
        3,68,34,0,353,351,1,0,0,0,354,357,1,0,0,0,355,353,1,0,0,0,355,356,
        1,0,0,0,356,67,1,0,0,0,357,355,1,0,0,0,358,363,3,70,35,0,359,360,
        5,45,0,0,360,362,3,70,35,0,361,359,1,0,0,0,362,365,1,0,0,0,363,361,
        1,0,0,0,363,364,1,0,0,0,364,69,1,0,0,0,365,363,1,0,0,0,366,371,3,
        72,36,0,367,368,5,46,0,0,368,370,3,72,36,0,369,367,1,0,0,0,370,373,
        1,0,0,0,371,369,1,0,0,0,371,372,1,0,0,0,372,71,1,0,0,0,373,371,1,
        0,0,0,374,379,3,74,37,0,375,376,5,44,0,0,376,378,3,74,37,0,377,375,
        1,0,0,0,378,381,1,0,0,0,379,377,1,0,0,0,379,380,1,0,0,0,380,73,1,
        0,0,0,381,379,1,0,0,0,382,387,3,76,38,0,383,384,7,1,0,0,384,386,
        3,76,38,0,385,383,1,0,0,0,386,389,1,0,0,0,387,385,1,0,0,0,387,388,
        1,0,0,0,388,75,1,0,0,0,389,387,1,0,0,0,390,395,3,78,39,0,391,392,
        7,2,0,0,392,394,3,78,39,0,393,391,1,0,0,0,394,397,1,0,0,0,395,393,
        1,0,0,0,395,396,1,0,0,0,396,77,1,0,0,0,397,395,1,0,0,0,398,403,3,
        80,40,0,399,400,7,3,0,0,400,402,3,80,40,0,401,399,1,0,0,0,402,405,
        1,0,0,0,403,401,1,0,0,0,403,404,1,0,0,0,404,79,1,0,0,0,405,403,1,
        0,0,0,406,411,3,82,41,0,407,408,7,4,0,0,408,410,3,82,41,0,409,407,
        1,0,0,0,410,413,1,0,0,0,411,409,1,0,0,0,411,412,1,0,0,0,412,81,1,
        0,0,0,413,411,1,0,0,0,414,419,3,84,42,0,415,416,7,5,0,0,416,418,
        3,84,42,0,417,415,1,0,0,0,418,421,1,0,0,0,419,417,1,0,0,0,419,420,
        1,0,0,0,420,83,1,0,0,0,421,419,1,0,0,0,422,445,3,86,43,0,423,424,
        7,6,0,0,424,445,3,84,42,0,425,426,5,61,0,0,426,428,3,94,47,0,427,
        429,3,26,13,0,428,427,1,0,0,0,428,429,1,0,0,0,429,430,1,0,0,0,430,
        431,5,62,0,0,431,432,3,84,42,0,432,445,1,0,0,0,433,442,5,18,0,0,
        434,435,5,61,0,0,435,437,3,94,47,0,436,438,3,26,13,0,437,436,1,0,
        0,0,437,438,1,0,0,0,438,439,1,0,0,0,439,440,5,62,0,0,440,443,1,0,
        0,0,441,443,3,84,42,0,442,434,1,0,0,0,442,441,1,0,0,0,443,445,1,
        0,0,0,444,422,1,0,0,0,444,423,1,0,0,0,444,425,1,0,0,0,444,433,1,
        0,0,0,445,85,1,0,0,0,446,450,3,92,46,0,447,449,3,88,44,0,448,447,
        1,0,0,0,449,452,1,0,0,0,450,448,1,0,0,0,450,451,1,0,0,0,451,87,1,
        0,0,0,452,450,1,0,0,0,453,454,5,65,0,0,454,455,3,56,28,0,455,456,
        5,66,0,0,456,469,1,0,0,0,457,459,5,61,0,0,458,460,3,90,45,0,459,
        458,1,0,0,0,459,460,1,0,0,0,460,461,1,0,0,0,461,469,5,62,0,0,462,
        463,5,68,0,0,463,469,5,70,0,0,464,465,5,67,0,0,465,469,5,70,0,0,
        466,469,5,24,0,0,467,469,5,25,0,0,468,453,1,0,0,0,468,457,1,0,0,
        0,468,462,1,0,0,0,468,464,1,0,0,0,468,466,1,0,0,0,468,467,1,0,0,
        0,469,89,1,0,0,0,470,475,3,58,29,0,471,472,5,59,0,0,472,474,3,58,
        29,0,473,471,1,0,0,0,474,477,1,0,0,0,475,473,1,0,0,0,475,476,1,0,
        0,0,476,91,1,0,0,0,477,475,1,0,0,0,478,489,5,70,0,0,479,489,5,71,
        0,0,480,489,5,72,0,0,481,489,5,73,0,0,482,489,5,74,0,0,483,489,5,
        19,0,0,484,485,5,61,0,0,485,486,3,56,28,0,486,487,5,62,0,0,487,489,
        1,0,0,0,488,478,1,0,0,0,488,479,1,0,0,0,488,480,1,0,0,0,488,481,
        1,0,0,0,488,482,1,0,0,0,488,483,1,0,0,0,488,484,1,0,0,0,489,93,1,
        0,0,0,490,492,7,7,0,0,491,490,1,0,0,0,491,492,1,0,0,0,492,508,1,
        0,0,0,493,509,5,3,0,0,494,496,5,8,0,0,495,497,5,1,0,0,496,495,1,
        0,0,0,496,497,1,0,0,0,497,509,1,0,0,0,498,499,5,9,0,0,499,501,5,
        9,0,0,500,502,5,1,0,0,501,500,1,0,0,0,501,502,1,0,0,0,502,509,1,
        0,0,0,503,505,5,9,0,0,504,506,5,1,0,0,505,504,1,0,0,0,505,506,1,
        0,0,0,506,509,1,0,0,0,507,509,5,1,0,0,508,493,1,0,0,0,508,494,1,
        0,0,0,508,498,1,0,0,0,508,503,1,0,0,0,508,507,1,0,0,0,509,517,1,
        0,0,0,510,517,5,6,0,0,511,517,5,7,0,0,512,517,5,2,0,0,513,517,5,
        5,0,0,514,517,5,4,0,0,515,517,3,96,48,0,516,491,1,0,0,0,516,510,
        1,0,0,0,516,511,1,0,0,0,516,512,1,0,0,0,516,513,1,0,0,0,516,514,
        1,0,0,0,516,515,1,0,0,0,517,95,1,0,0,0,518,519,5,23,0,0,519,528,
        5,70,0,0,520,524,5,63,0,0,521,523,3,98,49,0,522,521,1,0,0,0,523,
        526,1,0,0,0,524,522,1,0,0,0,524,525,1,0,0,0,525,527,1,0,0,0,526,
        524,1,0,0,0,527,529,5,64,0,0,528,520,1,0,0,0,528,529,1,0,0,0,529,
        540,1,0,0,0,530,531,5,23,0,0,531,535,5,63,0,0,532,534,3,98,49,0,
        533,532,1,0,0,0,534,537,1,0,0,0,535,533,1,0,0,0,535,536,1,0,0,0,
        536,538,1,0,0,0,537,535,1,0,0,0,538,540,5,64,0,0,539,518,1,0,0,0,
        539,530,1,0,0,0,540,97,1,0,0,0,541,542,3,94,47,0,542,547,3,100,50,
        0,543,544,5,59,0,0,544,546,3,100,50,0,545,543,1,0,0,0,546,549,1,
        0,0,0,547,545,1,0,0,0,547,548,1,0,0,0,548,550,1,0,0,0,549,547,1,
        0,0,0,550,551,5,60,0,0,551,99,1,0,0,0,552,554,3,26,13,0,553,552,
        1,0,0,0,553,554,1,0,0,0,554,555,1,0,0,0,555,557,5,70,0,0,556,558,
        3,28,14,0,557,556,1,0,0,0,557,558,1,0,0,0,558,101,1,0,0,0,68,105,
        112,116,121,128,133,143,148,151,154,160,167,174,181,185,189,193,
        202,206,208,211,216,220,225,239,253,258,269,288,292,296,303,307,
        322,330,340,347,355,363,371,379,387,395,403,411,419,428,437,442,
        444,450,459,468,475,488,491,496,501,505,508,516,524,528,535,539,
        547,553,557
    ]

class SimpleCParser ( Parser ):

    grammarFileName = "SimpleC.g4"

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    sharedContextCache = PredictionContextCache()

    literalNames = [ "<INVALID>", "'int'", "'float'", "'char'", "'void'", 
                     "'double'", "'signed'", "'unsigned'", "'short'", "'long'", 
                     "'return'", "'if'", "'else'", "'while'", "'do'", "'for'", 
                     "'break'", "'continue'", "'sizeof'", "'NULL'", "'switch'", 
                     "'case'", "'default'", "'struct'", "'++'", "'--'", 
                     "'<<='", "'>>='", "'+='", "'-='", "'*='", "'/='", "'%='", 
                     "'&='", "'|='", "'^='", "'<<'", "'>>'", "'=='", "'!='", 
                     "'<='", "'>='", "'&&'", "'||'", "'&'", "'|'", "'^'", 
                     "'~'", "'+'", "'-'", "'*'", "'/'", "'%'", "'<'", "'>'", 
                     "'!'", "'='", "'?'", "':'", "','", "';'", "'('", "')'", 
                     "'{'", "'}'", "'['", "']'", "'->'", "'.'" ]

    symbolicNames = [ "<INVALID>", "INT", "FLOAT", "CHAR", "VOID", "DOUBLE", 
                      "SIGNED", "UNSIGNED", "SHORT", "LONG", "RETURN", "IF", 
                      "ELSE", "WHILE", "DO", "FOR", "BREAK", "CONTINUE", 
                      "SIZEOF", "NULL", "SWITCH", "CASE", "DEFAULT", "STRUCT", 
                      "INC", "DEC", "LSHIFT_ASSIGN", "RSHIFT_ASSIGN", "ADD_ASSIGN", 
                      "SUB_ASSIGN", "MUL_ASSIGN", "DIV_ASSIGN", "MOD_ASSIGN", 
                      "AND_ASSIGN", "OR_ASSIGN", "XOR_ASSIGN", "LSHIFT", 
                      "RSHIFT", "EQ", "NEQ", "LTE", "GTE", "AND", "OR", 
                      "AMP", "PIPE", "CARET", "TILDE", "PLUS", "MINUS", 
                      "MUL", "DIV", "MOD", "LT", "GT", "NOT", "ASSIGN", 
                      "QUESTION", "COLON", "COMMA", "SEMI", "LPAREN", "RPAREN", 
                      "LBRACE", "RBRACE", "LBRACK", "RBRACK", "ARROW", "DOT", 
                      "PREPROCESSOR_DIRECTIVE", "IDENTIFIER", "INTEGER", 
                      "FLOAT_LITERAL", "CHAR_LITERAL", "STRING_LITERAL", 
                      "WS", "LINE_COMMENT", "BLOCK_COMMENT", "ERROR_CHAR" ]

    RULE_program = 0
    RULE_topLevelItem = 1
    RULE_functionDeclaration = 2
    RULE_functionDef = 3
    RULE_paramList = 4
    RULE_param = 5
    RULE_block = 6
    RULE_blockItem = 7
    RULE_declaration = 8
    RULE_declarationNoSemi = 9
    RULE_initDeclaratorList = 10
    RULE_initDeclarator = 11
    RULE_initializer = 12
    RULE_pointer = 13
    RULE_arraySuffix = 14
    RULE_statement = 15
    RULE_switchStatement = 16
    RULE_labeledStatement = 17
    RULE_emptyStatement = 18
    RULE_exprStatement = 19
    RULE_ifStatement = 20
    RULE_whileStatement = 21
    RULE_doWhileStatement = 22
    RULE_forStatement = 23
    RULE_forInit = 24
    RULE_returnStatement = 25
    RULE_breakStatement = 26
    RULE_continueStatement = 27
    RULE_expression = 28
    RULE_assignmentExpression = 29
    RULE_assignmentOperator = 30
    RULE_conditionalExpression = 31
    RULE_logicalOrExpression = 32
    RULE_logicalAndExpression = 33
    RULE_inclusiveOrExpression = 34
    RULE_exclusiveOrExpression = 35
    RULE_andExpression = 36
    RULE_equalityExpression = 37
    RULE_relationalExpression = 38
    RULE_shiftExpression = 39
    RULE_additiveExpression = 40
    RULE_multiplicativeExpression = 41
    RULE_unaryExpression = 42
    RULE_postfixExpression = 43
    RULE_postfixPart = 44
    RULE_argumentList = 45
    RULE_primaryExpression = 46
    RULE_typeSpecifier = 47
    RULE_structSpecifier = 48
    RULE_structMemberDeclaration = 49
    RULE_structDeclarator = 50

    ruleNames =  [ "program", "topLevelItem", "functionDeclaration", "functionDef", 
                   "paramList", "param", "block", "blockItem", "declaration", 
                   "declarationNoSemi", "initDeclaratorList", "initDeclarator", 
                   "initializer", "pointer", "arraySuffix", "statement", 
                   "switchStatement", "labeledStatement", "emptyStatement", 
                   "exprStatement", "ifStatement", "whileStatement", "doWhileStatement", 
                   "forStatement", "forInit", "returnStatement", "breakStatement", 
                   "continueStatement", "expression", "assignmentExpression", 
                   "assignmentOperator", "conditionalExpression", "logicalOrExpression", 
                   "logicalAndExpression", "inclusiveOrExpression", "exclusiveOrExpression", 
                   "andExpression", "equalityExpression", "relationalExpression", 
                   "shiftExpression", "additiveExpression", "multiplicativeExpression", 
                   "unaryExpression", "postfixExpression", "postfixPart", 
                   "argumentList", "primaryExpression", "typeSpecifier", 
                   "structSpecifier", "structMemberDeclaration", "structDeclarator" ]

    EOF = Token.EOF
    INT=1
    FLOAT=2
    CHAR=3
    VOID=4
    DOUBLE=5
    SIGNED=6
    UNSIGNED=7
    SHORT=8
    LONG=9
    RETURN=10
    IF=11
    ELSE=12
    WHILE=13
    DO=14
    FOR=15
    BREAK=16
    CONTINUE=17
    SIZEOF=18
    NULL=19
    SWITCH=20
    CASE=21
    DEFAULT=22
    STRUCT=23
    INC=24
    DEC=25
    LSHIFT_ASSIGN=26
    RSHIFT_ASSIGN=27
    ADD_ASSIGN=28
    SUB_ASSIGN=29
    MUL_ASSIGN=30
    DIV_ASSIGN=31
    MOD_ASSIGN=32
    AND_ASSIGN=33
    OR_ASSIGN=34
    XOR_ASSIGN=35
    LSHIFT=36
    RSHIFT=37
    EQ=38
    NEQ=39
    LTE=40
    GTE=41
    AND=42
    OR=43
    AMP=44
    PIPE=45
    CARET=46
    TILDE=47
    PLUS=48
    MINUS=49
    MUL=50
    DIV=51
    MOD=52
    LT=53
    GT=54
    NOT=55
    ASSIGN=56
    QUESTION=57
    COLON=58
    COMMA=59
    SEMI=60
    LPAREN=61
    RPAREN=62
    LBRACE=63
    RBRACE=64
    LBRACK=65
    RBRACK=66
    ARROW=67
    DOT=68
    PREPROCESSOR_DIRECTIVE=69
    IDENTIFIER=70
    INTEGER=71
    FLOAT_LITERAL=72
    CHAR_LITERAL=73
    STRING_LITERAL=74
    WS=75
    LINE_COMMENT=76
    BLOCK_COMMENT=77
    ERROR_CHAR=78

    def __init__(self, input:TokenStream, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.13.2")
        self._interp = ParserATNSimulator(self, self.atn, self.decisionsToDFA, self.sharedContextCache)
        self._predicates = None




    class ProgramContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def EOF(self):
            return self.getToken(SimpleCParser.EOF, 0)

        def topLevelItem(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(SimpleCParser.TopLevelItemContext)
            else:
                return self.getTypedRuleContext(SimpleCParser.TopLevelItemContext,i)


        def getRuleIndex(self):
            return SimpleCParser.RULE_program

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterProgram" ):
                listener.enterProgram(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitProgram" ):
                listener.exitProgram(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitProgram" ):
                return visitor.visitProgram(self)
            else:
                return visitor.visitChildren(self)




    def program(self):

        localctx = SimpleCParser.ProgramContext(self, self._ctx, self.state)
        self.enterRule(localctx, 0, self.RULE_program)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 103 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 102
                self.topLevelItem()
                self.state = 105 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not ((((_la) & ~0x3f) == 0 and ((1 << _la) & 8389630) != 0)):
                    break

            self.state = 107
            self.match(SimpleCParser.EOF)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class TopLevelItemContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def functionDef(self):
            return self.getTypedRuleContext(SimpleCParser.FunctionDefContext,0)


        def functionDeclaration(self):
            return self.getTypedRuleContext(SimpleCParser.FunctionDeclarationContext,0)


        def declaration(self):
            return self.getTypedRuleContext(SimpleCParser.DeclarationContext,0)


        def getRuleIndex(self):
            return SimpleCParser.RULE_topLevelItem

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterTopLevelItem" ):
                listener.enterTopLevelItem(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitTopLevelItem" ):
                listener.exitTopLevelItem(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitTopLevelItem" ):
                return visitor.visitTopLevelItem(self)
            else:
                return visitor.visitChildren(self)




    def topLevelItem(self):

        localctx = SimpleCParser.TopLevelItemContext(self, self._ctx, self.state)
        self.enterRule(localctx, 2, self.RULE_topLevelItem)
        try:
            self.state = 112
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,1,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 109
                self.functionDef()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 110
                self.functionDeclaration()
                pass

            elif la_ == 3:
                self.enterOuterAlt(localctx, 3)
                self.state = 111
                self.declaration()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class FunctionDeclarationContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def typeSpecifier(self):
            return self.getTypedRuleContext(SimpleCParser.TypeSpecifierContext,0)


        def IDENTIFIER(self):
            return self.getToken(SimpleCParser.IDENTIFIER, 0)

        def LPAREN(self):
            return self.getToken(SimpleCParser.LPAREN, 0)

        def RPAREN(self):
            return self.getToken(SimpleCParser.RPAREN, 0)

        def SEMI(self):
            return self.getToken(SimpleCParser.SEMI, 0)

        def pointer(self):
            return self.getTypedRuleContext(SimpleCParser.PointerContext,0)


        def paramList(self):
            return self.getTypedRuleContext(SimpleCParser.ParamListContext,0)


        def getRuleIndex(self):
            return SimpleCParser.RULE_functionDeclaration

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterFunctionDeclaration" ):
                listener.enterFunctionDeclaration(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitFunctionDeclaration" ):
                listener.exitFunctionDeclaration(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitFunctionDeclaration" ):
                return visitor.visitFunctionDeclaration(self)
            else:
                return visitor.visitChildren(self)




    def functionDeclaration(self):

        localctx = SimpleCParser.FunctionDeclarationContext(self, self._ctx, self.state)
        self.enterRule(localctx, 4, self.RULE_functionDeclaration)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 114
            self.typeSpecifier()
            self.state = 116
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==50:
                self.state = 115
                self.pointer()


            self.state = 118
            self.match(SimpleCParser.IDENTIFIER)
            self.state = 119
            self.match(SimpleCParser.LPAREN)
            self.state = 121
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if (((_la) & ~0x3f) == 0 and ((1 << _la) & 8389630) != 0):
                self.state = 120
                self.paramList()


            self.state = 123
            self.match(SimpleCParser.RPAREN)
            self.state = 124
            self.match(SimpleCParser.SEMI)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class FunctionDefContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def typeSpecifier(self):
            return self.getTypedRuleContext(SimpleCParser.TypeSpecifierContext,0)


        def IDENTIFIER(self):
            return self.getToken(SimpleCParser.IDENTIFIER, 0)

        def LPAREN(self):
            return self.getToken(SimpleCParser.LPAREN, 0)

        def RPAREN(self):
            return self.getToken(SimpleCParser.RPAREN, 0)

        def block(self):
            return self.getTypedRuleContext(SimpleCParser.BlockContext,0)


        def pointer(self):
            return self.getTypedRuleContext(SimpleCParser.PointerContext,0)


        def paramList(self):
            return self.getTypedRuleContext(SimpleCParser.ParamListContext,0)


        def getRuleIndex(self):
            return SimpleCParser.RULE_functionDef

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterFunctionDef" ):
                listener.enterFunctionDef(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitFunctionDef" ):
                listener.exitFunctionDef(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitFunctionDef" ):
                return visitor.visitFunctionDef(self)
            else:
                return visitor.visitChildren(self)




    def functionDef(self):

        localctx = SimpleCParser.FunctionDefContext(self, self._ctx, self.state)
        self.enterRule(localctx, 6, self.RULE_functionDef)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 126
            self.typeSpecifier()
            self.state = 128
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==50:
                self.state = 127
                self.pointer()


            self.state = 130
            self.match(SimpleCParser.IDENTIFIER)
            self.state = 131
            self.match(SimpleCParser.LPAREN)
            self.state = 133
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if (((_la) & ~0x3f) == 0 and ((1 << _la) & 8389630) != 0):
                self.state = 132
                self.paramList()


            self.state = 135
            self.match(SimpleCParser.RPAREN)
            self.state = 136
            self.block()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ParamListContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def param(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(SimpleCParser.ParamContext)
            else:
                return self.getTypedRuleContext(SimpleCParser.ParamContext,i)


        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.COMMA)
            else:
                return self.getToken(SimpleCParser.COMMA, i)

        def getRuleIndex(self):
            return SimpleCParser.RULE_paramList

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterParamList" ):
                listener.enterParamList(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitParamList" ):
                listener.exitParamList(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitParamList" ):
                return visitor.visitParamList(self)
            else:
                return visitor.visitChildren(self)




    def paramList(self):

        localctx = SimpleCParser.ParamListContext(self, self._ctx, self.state)
        self.enterRule(localctx, 8, self.RULE_paramList)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 138
            self.param()
            self.state = 143
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==59:
                self.state = 139
                self.match(SimpleCParser.COMMA)
                self.state = 140
                self.param()
                self.state = 145
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ParamContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def typeSpecifier(self):
            return self.getTypedRuleContext(SimpleCParser.TypeSpecifierContext,0)


        def pointer(self):
            return self.getTypedRuleContext(SimpleCParser.PointerContext,0)


        def IDENTIFIER(self):
            return self.getToken(SimpleCParser.IDENTIFIER, 0)

        def arraySuffix(self):
            return self.getTypedRuleContext(SimpleCParser.ArraySuffixContext,0)


        def getRuleIndex(self):
            return SimpleCParser.RULE_param

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterParam" ):
                listener.enterParam(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitParam" ):
                listener.exitParam(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitParam" ):
                return visitor.visitParam(self)
            else:
                return visitor.visitChildren(self)




    def param(self):

        localctx = SimpleCParser.ParamContext(self, self._ctx, self.state)
        self.enterRule(localctx, 10, self.RULE_param)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 146
            self.typeSpecifier()
            self.state = 148
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==50:
                self.state = 147
                self.pointer()


            self.state = 151
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==70:
                self.state = 150
                self.match(SimpleCParser.IDENTIFIER)


            self.state = 154
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==65:
                self.state = 153
                self.arraySuffix()


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class BlockContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LBRACE(self):
            return self.getToken(SimpleCParser.LBRACE, 0)

        def RBRACE(self):
            return self.getToken(SimpleCParser.RBRACE, 0)

        def blockItem(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(SimpleCParser.BlockItemContext)
            else:
                return self.getTypedRuleContext(SimpleCParser.BlockItemContext,i)


        def getRuleIndex(self):
            return SimpleCParser.RULE_block

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterBlock" ):
                listener.enterBlock(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitBlock" ):
                listener.exitBlock(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitBlock" ):
                return visitor.visitBlock(self)
            else:
                return visitor.visitChildren(self)




    def block(self):

        localctx = SimpleCParser.BlockContext(self, self._ctx, self.state)
        self.enterRule(localctx, 12, self.RULE_block)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 156
            self.match(SimpleCParser.LBRACE)
            self.state = 160
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while (((_la) & ~0x3f) == 0 and ((1 << _la) & -5726450071436791810) != 0) or ((((_la - 70)) & ~0x3f) == 0 and ((1 << (_la - 70)) & 31) != 0):
                self.state = 157
                self.blockItem()
                self.state = 162
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 163
            self.match(SimpleCParser.RBRACE)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class BlockItemContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def declaration(self):
            return self.getTypedRuleContext(SimpleCParser.DeclarationContext,0)


        def statement(self):
            return self.getTypedRuleContext(SimpleCParser.StatementContext,0)


        def getRuleIndex(self):
            return SimpleCParser.RULE_blockItem

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterBlockItem" ):
                listener.enterBlockItem(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitBlockItem" ):
                listener.exitBlockItem(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitBlockItem" ):
                return visitor.visitBlockItem(self)
            else:
                return visitor.visitChildren(self)




    def blockItem(self):

        localctx = SimpleCParser.BlockItemContext(self, self._ctx, self.state)
        self.enterRule(localctx, 14, self.RULE_blockItem)
        try:
            self.state = 167
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [1, 2, 3, 4, 5, 6, 7, 8, 9, 23]:
                self.enterOuterAlt(localctx, 1)
                self.state = 165
                self.declaration()
                pass
            elif token in [10, 11, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 24, 25, 44, 47, 48, 49, 50, 55, 60, 61, 63, 70, 71, 72, 73, 74]:
                self.enterOuterAlt(localctx, 2)
                self.state = 166
                self.statement()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class DeclarationContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def declarationNoSemi(self):
            return self.getTypedRuleContext(SimpleCParser.DeclarationNoSemiContext,0)


        def SEMI(self):
            return self.getToken(SimpleCParser.SEMI, 0)

        def getRuleIndex(self):
            return SimpleCParser.RULE_declaration

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterDeclaration" ):
                listener.enterDeclaration(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitDeclaration" ):
                listener.exitDeclaration(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitDeclaration" ):
                return visitor.visitDeclaration(self)
            else:
                return visitor.visitChildren(self)




    def declaration(self):

        localctx = SimpleCParser.DeclarationContext(self, self._ctx, self.state)
        self.enterRule(localctx, 16, self.RULE_declaration)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 169
            self.declarationNoSemi()
            self.state = 170
            self.match(SimpleCParser.SEMI)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class DeclarationNoSemiContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def typeSpecifier(self):
            return self.getTypedRuleContext(SimpleCParser.TypeSpecifierContext,0)


        def initDeclaratorList(self):
            return self.getTypedRuleContext(SimpleCParser.InitDeclaratorListContext,0)


        def getRuleIndex(self):
            return SimpleCParser.RULE_declarationNoSemi

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterDeclarationNoSemi" ):
                listener.enterDeclarationNoSemi(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitDeclarationNoSemi" ):
                listener.exitDeclarationNoSemi(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitDeclarationNoSemi" ):
                return visitor.visitDeclarationNoSemi(self)
            else:
                return visitor.visitChildren(self)




    def declarationNoSemi(self):

        localctx = SimpleCParser.DeclarationNoSemiContext(self, self._ctx, self.state)
        self.enterRule(localctx, 18, self.RULE_declarationNoSemi)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 172
            self.typeSpecifier()
            self.state = 174
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==50 or _la==70:
                self.state = 173
                self.initDeclaratorList()


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class InitDeclaratorListContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def initDeclarator(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(SimpleCParser.InitDeclaratorContext)
            else:
                return self.getTypedRuleContext(SimpleCParser.InitDeclaratorContext,i)


        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.COMMA)
            else:
                return self.getToken(SimpleCParser.COMMA, i)

        def getRuleIndex(self):
            return SimpleCParser.RULE_initDeclaratorList

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterInitDeclaratorList" ):
                listener.enterInitDeclaratorList(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitInitDeclaratorList" ):
                listener.exitInitDeclaratorList(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitInitDeclaratorList" ):
                return visitor.visitInitDeclaratorList(self)
            else:
                return visitor.visitChildren(self)




    def initDeclaratorList(self):

        localctx = SimpleCParser.InitDeclaratorListContext(self, self._ctx, self.state)
        self.enterRule(localctx, 20, self.RULE_initDeclaratorList)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 176
            self.initDeclarator()
            self.state = 181
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==59:
                self.state = 177
                self.match(SimpleCParser.COMMA)
                self.state = 178
                self.initDeclarator()
                self.state = 183
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class InitDeclaratorContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def IDENTIFIER(self):
            return self.getToken(SimpleCParser.IDENTIFIER, 0)

        def pointer(self):
            return self.getTypedRuleContext(SimpleCParser.PointerContext,0)


        def arraySuffix(self):
            return self.getTypedRuleContext(SimpleCParser.ArraySuffixContext,0)


        def ASSIGN(self):
            return self.getToken(SimpleCParser.ASSIGN, 0)

        def initializer(self):
            return self.getTypedRuleContext(SimpleCParser.InitializerContext,0)


        def getRuleIndex(self):
            return SimpleCParser.RULE_initDeclarator

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterInitDeclarator" ):
                listener.enterInitDeclarator(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitInitDeclarator" ):
                listener.exitInitDeclarator(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitInitDeclarator" ):
                return visitor.visitInitDeclarator(self)
            else:
                return visitor.visitChildren(self)




    def initDeclarator(self):

        localctx = SimpleCParser.InitDeclaratorContext(self, self._ctx, self.state)
        self.enterRule(localctx, 22, self.RULE_initDeclarator)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 185
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==50:
                self.state = 184
                self.pointer()


            self.state = 187
            self.match(SimpleCParser.IDENTIFIER)
            self.state = 189
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==65:
                self.state = 188
                self.arraySuffix()


            self.state = 193
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==56:
                self.state = 191
                self.match(SimpleCParser.ASSIGN)
                self.state = 192
                self.initializer()


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class InitializerContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def assignmentExpression(self):
            return self.getTypedRuleContext(SimpleCParser.AssignmentExpressionContext,0)


        def LBRACE(self):
            return self.getToken(SimpleCParser.LBRACE, 0)

        def RBRACE(self):
            return self.getToken(SimpleCParser.RBRACE, 0)

        def initializer(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(SimpleCParser.InitializerContext)
            else:
                return self.getTypedRuleContext(SimpleCParser.InitializerContext,i)


        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.COMMA)
            else:
                return self.getToken(SimpleCParser.COMMA, i)

        def getRuleIndex(self):
            return SimpleCParser.RULE_initializer

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterInitializer" ):
                listener.enterInitializer(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitInitializer" ):
                listener.exitInitializer(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitInitializer" ):
                return visitor.visitInitializer(self)
            else:
                return visitor.visitChildren(self)




    def initializer(self):

        localctx = SimpleCParser.InitializerContext(self, self._ctx, self.state)
        self.enterRule(localctx, 24, self.RULE_initializer)
        self._la = 0 # Token type
        try:
            self.state = 211
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [18, 19, 24, 25, 44, 47, 48, 49, 50, 55, 61, 70, 71, 72, 73, 74]:
                self.enterOuterAlt(localctx, 1)
                self.state = 195
                self.assignmentExpression()
                pass
            elif token in [63]:
                self.enterOuterAlt(localctx, 2)
                self.state = 196
                self.match(SimpleCParser.LBRACE)
                self.state = 208
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if ((((_la - 18)) & ~0x3f) == 0 and ((1 << (_la - 18)) & 139655714472722627) != 0):
                    self.state = 197
                    self.initializer()
                    self.state = 202
                    self._errHandler.sync(self)
                    _alt = self._interp.adaptivePredict(self._input,17,self._ctx)
                    while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                        if _alt==1:
                            self.state = 198
                            self.match(SimpleCParser.COMMA)
                            self.state = 199
                            self.initializer() 
                        self.state = 204
                        self._errHandler.sync(self)
                        _alt = self._interp.adaptivePredict(self._input,17,self._ctx)

                    self.state = 206
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)
                    if _la==59:
                        self.state = 205
                        self.match(SimpleCParser.COMMA)




                self.state = 210
                self.match(SimpleCParser.RBRACE)
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class PointerContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def MUL(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.MUL)
            else:
                return self.getToken(SimpleCParser.MUL, i)

        def getRuleIndex(self):
            return SimpleCParser.RULE_pointer

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterPointer" ):
                listener.enterPointer(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitPointer" ):
                listener.exitPointer(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitPointer" ):
                return visitor.visitPointer(self)
            else:
                return visitor.visitChildren(self)




    def pointer(self):

        localctx = SimpleCParser.PointerContext(self, self._ctx, self.state)
        self.enterRule(localctx, 26, self.RULE_pointer)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 214 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 213
                self.match(SimpleCParser.MUL)
                self.state = 216 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not (_la==50):
                    break

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ArraySuffixContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LBRACK(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.LBRACK)
            else:
                return self.getToken(SimpleCParser.LBRACK, i)

        def RBRACK(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.RBRACK)
            else:
                return self.getToken(SimpleCParser.RBRACK, i)

        def expression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(SimpleCParser.ExpressionContext)
            else:
                return self.getTypedRuleContext(SimpleCParser.ExpressionContext,i)


        def getRuleIndex(self):
            return SimpleCParser.RULE_arraySuffix

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterArraySuffix" ):
                listener.enterArraySuffix(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitArraySuffix" ):
                listener.exitArraySuffix(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitArraySuffix" ):
                return visitor.visitArraySuffix(self)
            else:
                return visitor.visitChildren(self)




    def arraySuffix(self):

        localctx = SimpleCParser.ArraySuffixContext(self, self._ctx, self.state)
        self.enterRule(localctx, 28, self.RULE_arraySuffix)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 223 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 218
                self.match(SimpleCParser.LBRACK)
                self.state = 220
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if ((((_la - 18)) & ~0x3f) == 0 and ((1 << (_la - 18)) & 139620530100633795) != 0):
                    self.state = 219
                    self.expression()


                self.state = 222
                self.match(SimpleCParser.RBRACK)
                self.state = 225 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not (_la==65):
                    break

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class StatementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def emptyStatement(self):
            return self.getTypedRuleContext(SimpleCParser.EmptyStatementContext,0)


        def exprStatement(self):
            return self.getTypedRuleContext(SimpleCParser.ExprStatementContext,0)


        def ifStatement(self):
            return self.getTypedRuleContext(SimpleCParser.IfStatementContext,0)


        def whileStatement(self):
            return self.getTypedRuleContext(SimpleCParser.WhileStatementContext,0)


        def doWhileStatement(self):
            return self.getTypedRuleContext(SimpleCParser.DoWhileStatementContext,0)


        def forStatement(self):
            return self.getTypedRuleContext(SimpleCParser.ForStatementContext,0)


        def switchStatement(self):
            return self.getTypedRuleContext(SimpleCParser.SwitchStatementContext,0)


        def labeledStatement(self):
            return self.getTypedRuleContext(SimpleCParser.LabeledStatementContext,0)


        def returnStatement(self):
            return self.getTypedRuleContext(SimpleCParser.ReturnStatementContext,0)


        def breakStatement(self):
            return self.getTypedRuleContext(SimpleCParser.BreakStatementContext,0)


        def continueStatement(self):
            return self.getTypedRuleContext(SimpleCParser.ContinueStatementContext,0)


        def block(self):
            return self.getTypedRuleContext(SimpleCParser.BlockContext,0)


        def getRuleIndex(self):
            return SimpleCParser.RULE_statement

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterStatement" ):
                listener.enterStatement(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitStatement" ):
                listener.exitStatement(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitStatement" ):
                return visitor.visitStatement(self)
            else:
                return visitor.visitChildren(self)




    def statement(self):

        localctx = SimpleCParser.StatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 30, self.RULE_statement)
        try:
            self.state = 239
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,24,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 227
                self.emptyStatement()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 228
                self.exprStatement()
                pass

            elif la_ == 3:
                self.enterOuterAlt(localctx, 3)
                self.state = 229
                self.ifStatement()
                pass

            elif la_ == 4:
                self.enterOuterAlt(localctx, 4)
                self.state = 230
                self.whileStatement()
                pass

            elif la_ == 5:
                self.enterOuterAlt(localctx, 5)
                self.state = 231
                self.doWhileStatement()
                pass

            elif la_ == 6:
                self.enterOuterAlt(localctx, 6)
                self.state = 232
                self.forStatement()
                pass

            elif la_ == 7:
                self.enterOuterAlt(localctx, 7)
                self.state = 233
                self.switchStatement()
                pass

            elif la_ == 8:
                self.enterOuterAlt(localctx, 8)
                self.state = 234
                self.labeledStatement()
                pass

            elif la_ == 9:
                self.enterOuterAlt(localctx, 9)
                self.state = 235
                self.returnStatement()
                pass

            elif la_ == 10:
                self.enterOuterAlt(localctx, 10)
                self.state = 236
                self.breakStatement()
                pass

            elif la_ == 11:
                self.enterOuterAlt(localctx, 11)
                self.state = 237
                self.continueStatement()
                pass

            elif la_ == 12:
                self.enterOuterAlt(localctx, 12)
                self.state = 238
                self.block()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class SwitchStatementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def SWITCH(self):
            return self.getToken(SimpleCParser.SWITCH, 0)

        def LPAREN(self):
            return self.getToken(SimpleCParser.LPAREN, 0)

        def expression(self):
            return self.getTypedRuleContext(SimpleCParser.ExpressionContext,0)


        def RPAREN(self):
            return self.getToken(SimpleCParser.RPAREN, 0)

        def statement(self):
            return self.getTypedRuleContext(SimpleCParser.StatementContext,0)


        def getRuleIndex(self):
            return SimpleCParser.RULE_switchStatement

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterSwitchStatement" ):
                listener.enterSwitchStatement(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitSwitchStatement" ):
                listener.exitSwitchStatement(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitSwitchStatement" ):
                return visitor.visitSwitchStatement(self)
            else:
                return visitor.visitChildren(self)




    def switchStatement(self):

        localctx = SimpleCParser.SwitchStatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 32, self.RULE_switchStatement)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 241
            self.match(SimpleCParser.SWITCH)
            self.state = 242
            self.match(SimpleCParser.LPAREN)
            self.state = 243
            self.expression()
            self.state = 244
            self.match(SimpleCParser.RPAREN)
            self.state = 245
            self.statement()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class LabeledStatementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def CASE(self):
            return self.getToken(SimpleCParser.CASE, 0)

        def conditionalExpression(self):
            return self.getTypedRuleContext(SimpleCParser.ConditionalExpressionContext,0)


        def COLON(self):
            return self.getToken(SimpleCParser.COLON, 0)

        def DEFAULT(self):
            return self.getToken(SimpleCParser.DEFAULT, 0)

        def getRuleIndex(self):
            return SimpleCParser.RULE_labeledStatement

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterLabeledStatement" ):
                listener.enterLabeledStatement(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitLabeledStatement" ):
                listener.exitLabeledStatement(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitLabeledStatement" ):
                return visitor.visitLabeledStatement(self)
            else:
                return visitor.visitChildren(self)




    def labeledStatement(self):

        localctx = SimpleCParser.LabeledStatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 34, self.RULE_labeledStatement)
        try:
            self.state = 253
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [21]:
                self.enterOuterAlt(localctx, 1)
                self.state = 247
                self.match(SimpleCParser.CASE)
                self.state = 248
                self.conditionalExpression()
                self.state = 249
                self.match(SimpleCParser.COLON)
                pass
            elif token in [22]:
                self.enterOuterAlt(localctx, 2)
                self.state = 251
                self.match(SimpleCParser.DEFAULT)
                self.state = 252
                self.match(SimpleCParser.COLON)
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class EmptyStatementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def SEMI(self):
            return self.getToken(SimpleCParser.SEMI, 0)

        def getRuleIndex(self):
            return SimpleCParser.RULE_emptyStatement

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterEmptyStatement" ):
                listener.enterEmptyStatement(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitEmptyStatement" ):
                listener.exitEmptyStatement(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitEmptyStatement" ):
                return visitor.visitEmptyStatement(self)
            else:
                return visitor.visitChildren(self)




    def emptyStatement(self):

        localctx = SimpleCParser.EmptyStatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 36, self.RULE_emptyStatement)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 255
            self.match(SimpleCParser.SEMI)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ExprStatementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def SEMI(self):
            return self.getToken(SimpleCParser.SEMI, 0)

        def expression(self):
            return self.getTypedRuleContext(SimpleCParser.ExpressionContext,0)


        def getRuleIndex(self):
            return SimpleCParser.RULE_exprStatement

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterExprStatement" ):
                listener.enterExprStatement(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitExprStatement" ):
                listener.exitExprStatement(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitExprStatement" ):
                return visitor.visitExprStatement(self)
            else:
                return visitor.visitChildren(self)




    def exprStatement(self):

        localctx = SimpleCParser.ExprStatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 38, self.RULE_exprStatement)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 258
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if ((((_la - 18)) & ~0x3f) == 0 and ((1 << (_la - 18)) & 139620530100633795) != 0):
                self.state = 257
                self.expression()


            self.state = 260
            self.match(SimpleCParser.SEMI)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class IfStatementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def IF(self):
            return self.getToken(SimpleCParser.IF, 0)

        def LPAREN(self):
            return self.getToken(SimpleCParser.LPAREN, 0)

        def expression(self):
            return self.getTypedRuleContext(SimpleCParser.ExpressionContext,0)


        def RPAREN(self):
            return self.getToken(SimpleCParser.RPAREN, 0)

        def statement(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(SimpleCParser.StatementContext)
            else:
                return self.getTypedRuleContext(SimpleCParser.StatementContext,i)


        def ELSE(self):
            return self.getToken(SimpleCParser.ELSE, 0)

        def getRuleIndex(self):
            return SimpleCParser.RULE_ifStatement

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterIfStatement" ):
                listener.enterIfStatement(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitIfStatement" ):
                listener.exitIfStatement(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitIfStatement" ):
                return visitor.visitIfStatement(self)
            else:
                return visitor.visitChildren(self)




    def ifStatement(self):

        localctx = SimpleCParser.IfStatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 40, self.RULE_ifStatement)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 262
            self.match(SimpleCParser.IF)
            self.state = 263
            self.match(SimpleCParser.LPAREN)
            self.state = 264
            self.expression()
            self.state = 265
            self.match(SimpleCParser.RPAREN)
            self.state = 266
            self.statement()
            self.state = 269
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,27,self._ctx)
            if la_ == 1:
                self.state = 267
                self.match(SimpleCParser.ELSE)
                self.state = 268
                self.statement()


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class WhileStatementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def WHILE(self):
            return self.getToken(SimpleCParser.WHILE, 0)

        def LPAREN(self):
            return self.getToken(SimpleCParser.LPAREN, 0)

        def expression(self):
            return self.getTypedRuleContext(SimpleCParser.ExpressionContext,0)


        def RPAREN(self):
            return self.getToken(SimpleCParser.RPAREN, 0)

        def statement(self):
            return self.getTypedRuleContext(SimpleCParser.StatementContext,0)


        def getRuleIndex(self):
            return SimpleCParser.RULE_whileStatement

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterWhileStatement" ):
                listener.enterWhileStatement(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitWhileStatement" ):
                listener.exitWhileStatement(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitWhileStatement" ):
                return visitor.visitWhileStatement(self)
            else:
                return visitor.visitChildren(self)




    def whileStatement(self):

        localctx = SimpleCParser.WhileStatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 42, self.RULE_whileStatement)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 271
            self.match(SimpleCParser.WHILE)
            self.state = 272
            self.match(SimpleCParser.LPAREN)
            self.state = 273
            self.expression()
            self.state = 274
            self.match(SimpleCParser.RPAREN)
            self.state = 275
            self.statement()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class DoWhileStatementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def DO(self):
            return self.getToken(SimpleCParser.DO, 0)

        def statement(self):
            return self.getTypedRuleContext(SimpleCParser.StatementContext,0)


        def WHILE(self):
            return self.getToken(SimpleCParser.WHILE, 0)

        def LPAREN(self):
            return self.getToken(SimpleCParser.LPAREN, 0)

        def expression(self):
            return self.getTypedRuleContext(SimpleCParser.ExpressionContext,0)


        def RPAREN(self):
            return self.getToken(SimpleCParser.RPAREN, 0)

        def SEMI(self):
            return self.getToken(SimpleCParser.SEMI, 0)

        def getRuleIndex(self):
            return SimpleCParser.RULE_doWhileStatement

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterDoWhileStatement" ):
                listener.enterDoWhileStatement(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitDoWhileStatement" ):
                listener.exitDoWhileStatement(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitDoWhileStatement" ):
                return visitor.visitDoWhileStatement(self)
            else:
                return visitor.visitChildren(self)




    def doWhileStatement(self):

        localctx = SimpleCParser.DoWhileStatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 44, self.RULE_doWhileStatement)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 277
            self.match(SimpleCParser.DO)
            self.state = 278
            self.statement()
            self.state = 279
            self.match(SimpleCParser.WHILE)
            self.state = 280
            self.match(SimpleCParser.LPAREN)
            self.state = 281
            self.expression()
            self.state = 282
            self.match(SimpleCParser.RPAREN)
            self.state = 283
            self.match(SimpleCParser.SEMI)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ForStatementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def FOR(self):
            return self.getToken(SimpleCParser.FOR, 0)

        def LPAREN(self):
            return self.getToken(SimpleCParser.LPAREN, 0)

        def SEMI(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.SEMI)
            else:
                return self.getToken(SimpleCParser.SEMI, i)

        def RPAREN(self):
            return self.getToken(SimpleCParser.RPAREN, 0)

        def statement(self):
            return self.getTypedRuleContext(SimpleCParser.StatementContext,0)


        def forInit(self):
            return self.getTypedRuleContext(SimpleCParser.ForInitContext,0)


        def expression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(SimpleCParser.ExpressionContext)
            else:
                return self.getTypedRuleContext(SimpleCParser.ExpressionContext,i)


        def getRuleIndex(self):
            return SimpleCParser.RULE_forStatement

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterForStatement" ):
                listener.enterForStatement(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitForStatement" ):
                listener.exitForStatement(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitForStatement" ):
                return visitor.visitForStatement(self)
            else:
                return visitor.visitChildren(self)




    def forStatement(self):

        localctx = SimpleCParser.ForStatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 46, self.RULE_forStatement)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 285
            self.match(SimpleCParser.FOR)
            self.state = 286
            self.match(SimpleCParser.LPAREN)
            self.state = 288
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if (((_la) & ~0x3f) == 0 and ((1 << _la) & 2344000460803539966) != 0) or ((((_la - 70)) & ~0x3f) == 0 and ((1 << (_la - 70)) & 31) != 0):
                self.state = 287
                self.forInit()


            self.state = 290
            self.match(SimpleCParser.SEMI)
            self.state = 292
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if ((((_la - 18)) & ~0x3f) == 0 and ((1 << (_la - 18)) & 139620530100633795) != 0):
                self.state = 291
                self.expression()


            self.state = 294
            self.match(SimpleCParser.SEMI)
            self.state = 296
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if ((((_la - 18)) & ~0x3f) == 0 and ((1 << (_la - 18)) & 139620530100633795) != 0):
                self.state = 295
                self.expression()


            self.state = 298
            self.match(SimpleCParser.RPAREN)
            self.state = 299
            self.statement()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ForInitContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def declarationNoSemi(self):
            return self.getTypedRuleContext(SimpleCParser.DeclarationNoSemiContext,0)


        def expression(self):
            return self.getTypedRuleContext(SimpleCParser.ExpressionContext,0)


        def getRuleIndex(self):
            return SimpleCParser.RULE_forInit

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterForInit" ):
                listener.enterForInit(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitForInit" ):
                listener.exitForInit(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitForInit" ):
                return visitor.visitForInit(self)
            else:
                return visitor.visitChildren(self)




    def forInit(self):

        localctx = SimpleCParser.ForInitContext(self, self._ctx, self.state)
        self.enterRule(localctx, 48, self.RULE_forInit)
        try:
            self.state = 303
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [1, 2, 3, 4, 5, 6, 7, 8, 9, 23]:
                self.enterOuterAlt(localctx, 1)
                self.state = 301
                self.declarationNoSemi()
                pass
            elif token in [18, 19, 24, 25, 44, 47, 48, 49, 50, 55, 61, 70, 71, 72, 73, 74]:
                self.enterOuterAlt(localctx, 2)
                self.state = 302
                self.expression()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ReturnStatementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def RETURN(self):
            return self.getToken(SimpleCParser.RETURN, 0)

        def SEMI(self):
            return self.getToken(SimpleCParser.SEMI, 0)

        def expression(self):
            return self.getTypedRuleContext(SimpleCParser.ExpressionContext,0)


        def getRuleIndex(self):
            return SimpleCParser.RULE_returnStatement

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterReturnStatement" ):
                listener.enterReturnStatement(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitReturnStatement" ):
                listener.exitReturnStatement(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitReturnStatement" ):
                return visitor.visitReturnStatement(self)
            else:
                return visitor.visitChildren(self)




    def returnStatement(self):

        localctx = SimpleCParser.ReturnStatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 50, self.RULE_returnStatement)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 305
            self.match(SimpleCParser.RETURN)
            self.state = 307
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if ((((_la - 18)) & ~0x3f) == 0 and ((1 << (_la - 18)) & 139620530100633795) != 0):
                self.state = 306
                self.expression()


            self.state = 309
            self.match(SimpleCParser.SEMI)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class BreakStatementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def BREAK(self):
            return self.getToken(SimpleCParser.BREAK, 0)

        def SEMI(self):
            return self.getToken(SimpleCParser.SEMI, 0)

        def getRuleIndex(self):
            return SimpleCParser.RULE_breakStatement

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterBreakStatement" ):
                listener.enterBreakStatement(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitBreakStatement" ):
                listener.exitBreakStatement(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitBreakStatement" ):
                return visitor.visitBreakStatement(self)
            else:
                return visitor.visitChildren(self)




    def breakStatement(self):

        localctx = SimpleCParser.BreakStatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 52, self.RULE_breakStatement)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 311
            self.match(SimpleCParser.BREAK)
            self.state = 312
            self.match(SimpleCParser.SEMI)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ContinueStatementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def CONTINUE(self):
            return self.getToken(SimpleCParser.CONTINUE, 0)

        def SEMI(self):
            return self.getToken(SimpleCParser.SEMI, 0)

        def getRuleIndex(self):
            return SimpleCParser.RULE_continueStatement

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterContinueStatement" ):
                listener.enterContinueStatement(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitContinueStatement" ):
                listener.exitContinueStatement(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitContinueStatement" ):
                return visitor.visitContinueStatement(self)
            else:
                return visitor.visitChildren(self)




    def continueStatement(self):

        localctx = SimpleCParser.ContinueStatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 54, self.RULE_continueStatement)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 314
            self.match(SimpleCParser.CONTINUE)
            self.state = 315
            self.match(SimpleCParser.SEMI)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def assignmentExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(SimpleCParser.AssignmentExpressionContext)
            else:
                return self.getTypedRuleContext(SimpleCParser.AssignmentExpressionContext,i)


        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.COMMA)
            else:
                return self.getToken(SimpleCParser.COMMA, i)

        def getRuleIndex(self):
            return SimpleCParser.RULE_expression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterExpression" ):
                listener.enterExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitExpression" ):
                listener.exitExpression(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitExpression" ):
                return visitor.visitExpression(self)
            else:
                return visitor.visitChildren(self)




    def expression(self):

        localctx = SimpleCParser.ExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 56, self.RULE_expression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 317
            self.assignmentExpression()
            self.state = 322
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==59:
                self.state = 318
                self.match(SimpleCParser.COMMA)
                self.state = 319
                self.assignmentExpression()
                self.state = 324
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class AssignmentExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def conditionalExpression(self):
            return self.getTypedRuleContext(SimpleCParser.ConditionalExpressionContext,0)


        def unaryExpression(self):
            return self.getTypedRuleContext(SimpleCParser.UnaryExpressionContext,0)


        def assignmentOperator(self):
            return self.getTypedRuleContext(SimpleCParser.AssignmentOperatorContext,0)


        def assignmentExpression(self):
            return self.getTypedRuleContext(SimpleCParser.AssignmentExpressionContext,0)


        def getRuleIndex(self):
            return SimpleCParser.RULE_assignmentExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterAssignmentExpression" ):
                listener.enterAssignmentExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitAssignmentExpression" ):
                listener.exitAssignmentExpression(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAssignmentExpression" ):
                return visitor.visitAssignmentExpression(self)
            else:
                return visitor.visitChildren(self)




    def assignmentExpression(self):

        localctx = SimpleCParser.AssignmentExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 58, self.RULE_assignmentExpression)
        try:
            self.state = 330
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,34,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 325
                self.conditionalExpression()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 326
                self.unaryExpression()
                self.state = 327
                self.assignmentOperator()
                self.state = 328
                self.assignmentExpression()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class AssignmentOperatorContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ASSIGN(self):
            return self.getToken(SimpleCParser.ASSIGN, 0)

        def ADD_ASSIGN(self):
            return self.getToken(SimpleCParser.ADD_ASSIGN, 0)

        def SUB_ASSIGN(self):
            return self.getToken(SimpleCParser.SUB_ASSIGN, 0)

        def MUL_ASSIGN(self):
            return self.getToken(SimpleCParser.MUL_ASSIGN, 0)

        def DIV_ASSIGN(self):
            return self.getToken(SimpleCParser.DIV_ASSIGN, 0)

        def MOD_ASSIGN(self):
            return self.getToken(SimpleCParser.MOD_ASSIGN, 0)

        def AND_ASSIGN(self):
            return self.getToken(SimpleCParser.AND_ASSIGN, 0)

        def OR_ASSIGN(self):
            return self.getToken(SimpleCParser.OR_ASSIGN, 0)

        def XOR_ASSIGN(self):
            return self.getToken(SimpleCParser.XOR_ASSIGN, 0)

        def LSHIFT_ASSIGN(self):
            return self.getToken(SimpleCParser.LSHIFT_ASSIGN, 0)

        def RSHIFT_ASSIGN(self):
            return self.getToken(SimpleCParser.RSHIFT_ASSIGN, 0)

        def getRuleIndex(self):
            return SimpleCParser.RULE_assignmentOperator

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterAssignmentOperator" ):
                listener.enterAssignmentOperator(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitAssignmentOperator" ):
                listener.exitAssignmentOperator(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAssignmentOperator" ):
                return visitor.visitAssignmentOperator(self)
            else:
                return visitor.visitChildren(self)




    def assignmentOperator(self):

        localctx = SimpleCParser.AssignmentOperatorContext(self, self._ctx, self.state)
        self.enterRule(localctx, 60, self.RULE_assignmentOperator)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 332
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 72057662690295808) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ConditionalExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def logicalOrExpression(self):
            return self.getTypedRuleContext(SimpleCParser.LogicalOrExpressionContext,0)


        def QUESTION(self):
            return self.getToken(SimpleCParser.QUESTION, 0)

        def expression(self):
            return self.getTypedRuleContext(SimpleCParser.ExpressionContext,0)


        def COLON(self):
            return self.getToken(SimpleCParser.COLON, 0)

        def conditionalExpression(self):
            return self.getTypedRuleContext(SimpleCParser.ConditionalExpressionContext,0)


        def getRuleIndex(self):
            return SimpleCParser.RULE_conditionalExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterConditionalExpression" ):
                listener.enterConditionalExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitConditionalExpression" ):
                listener.exitConditionalExpression(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitConditionalExpression" ):
                return visitor.visitConditionalExpression(self)
            else:
                return visitor.visitChildren(self)




    def conditionalExpression(self):

        localctx = SimpleCParser.ConditionalExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 62, self.RULE_conditionalExpression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 334
            self.logicalOrExpression()
            self.state = 340
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==57:
                self.state = 335
                self.match(SimpleCParser.QUESTION)
                self.state = 336
                self.expression()
                self.state = 337
                self.match(SimpleCParser.COLON)
                self.state = 338
                self.conditionalExpression()


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class LogicalOrExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def logicalAndExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(SimpleCParser.LogicalAndExpressionContext)
            else:
                return self.getTypedRuleContext(SimpleCParser.LogicalAndExpressionContext,i)


        def OR(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.OR)
            else:
                return self.getToken(SimpleCParser.OR, i)

        def getRuleIndex(self):
            return SimpleCParser.RULE_logicalOrExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterLogicalOrExpression" ):
                listener.enterLogicalOrExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitLogicalOrExpression" ):
                listener.exitLogicalOrExpression(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitLogicalOrExpression" ):
                return visitor.visitLogicalOrExpression(self)
            else:
                return visitor.visitChildren(self)




    def logicalOrExpression(self):

        localctx = SimpleCParser.LogicalOrExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 64, self.RULE_logicalOrExpression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 342
            self.logicalAndExpression()
            self.state = 347
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==43:
                self.state = 343
                self.match(SimpleCParser.OR)
                self.state = 344
                self.logicalAndExpression()
                self.state = 349
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class LogicalAndExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def inclusiveOrExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(SimpleCParser.InclusiveOrExpressionContext)
            else:
                return self.getTypedRuleContext(SimpleCParser.InclusiveOrExpressionContext,i)


        def AND(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.AND)
            else:
                return self.getToken(SimpleCParser.AND, i)

        def getRuleIndex(self):
            return SimpleCParser.RULE_logicalAndExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterLogicalAndExpression" ):
                listener.enterLogicalAndExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitLogicalAndExpression" ):
                listener.exitLogicalAndExpression(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitLogicalAndExpression" ):
                return visitor.visitLogicalAndExpression(self)
            else:
                return visitor.visitChildren(self)




    def logicalAndExpression(self):

        localctx = SimpleCParser.LogicalAndExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 66, self.RULE_logicalAndExpression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 350
            self.inclusiveOrExpression()
            self.state = 355
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==42:
                self.state = 351
                self.match(SimpleCParser.AND)
                self.state = 352
                self.inclusiveOrExpression()
                self.state = 357
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class InclusiveOrExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def exclusiveOrExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(SimpleCParser.ExclusiveOrExpressionContext)
            else:
                return self.getTypedRuleContext(SimpleCParser.ExclusiveOrExpressionContext,i)


        def PIPE(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.PIPE)
            else:
                return self.getToken(SimpleCParser.PIPE, i)

        def getRuleIndex(self):
            return SimpleCParser.RULE_inclusiveOrExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterInclusiveOrExpression" ):
                listener.enterInclusiveOrExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitInclusiveOrExpression" ):
                listener.exitInclusiveOrExpression(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitInclusiveOrExpression" ):
                return visitor.visitInclusiveOrExpression(self)
            else:
                return visitor.visitChildren(self)




    def inclusiveOrExpression(self):

        localctx = SimpleCParser.InclusiveOrExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 68, self.RULE_inclusiveOrExpression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 358
            self.exclusiveOrExpression()
            self.state = 363
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==45:
                self.state = 359
                self.match(SimpleCParser.PIPE)
                self.state = 360
                self.exclusiveOrExpression()
                self.state = 365
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ExclusiveOrExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def andExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(SimpleCParser.AndExpressionContext)
            else:
                return self.getTypedRuleContext(SimpleCParser.AndExpressionContext,i)


        def CARET(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.CARET)
            else:
                return self.getToken(SimpleCParser.CARET, i)

        def getRuleIndex(self):
            return SimpleCParser.RULE_exclusiveOrExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterExclusiveOrExpression" ):
                listener.enterExclusiveOrExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitExclusiveOrExpression" ):
                listener.exitExclusiveOrExpression(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitExclusiveOrExpression" ):
                return visitor.visitExclusiveOrExpression(self)
            else:
                return visitor.visitChildren(self)




    def exclusiveOrExpression(self):

        localctx = SimpleCParser.ExclusiveOrExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 70, self.RULE_exclusiveOrExpression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 366
            self.andExpression()
            self.state = 371
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==46:
                self.state = 367
                self.match(SimpleCParser.CARET)
                self.state = 368
                self.andExpression()
                self.state = 373
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class AndExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def equalityExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(SimpleCParser.EqualityExpressionContext)
            else:
                return self.getTypedRuleContext(SimpleCParser.EqualityExpressionContext,i)


        def AMP(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.AMP)
            else:
                return self.getToken(SimpleCParser.AMP, i)

        def getRuleIndex(self):
            return SimpleCParser.RULE_andExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterAndExpression" ):
                listener.enterAndExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitAndExpression" ):
                listener.exitAndExpression(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAndExpression" ):
                return visitor.visitAndExpression(self)
            else:
                return visitor.visitChildren(self)




    def andExpression(self):

        localctx = SimpleCParser.AndExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 72, self.RULE_andExpression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 374
            self.equalityExpression()
            self.state = 379
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==44:
                self.state = 375
                self.match(SimpleCParser.AMP)
                self.state = 376
                self.equalityExpression()
                self.state = 381
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class EqualityExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def relationalExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(SimpleCParser.RelationalExpressionContext)
            else:
                return self.getTypedRuleContext(SimpleCParser.RelationalExpressionContext,i)


        def EQ(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.EQ)
            else:
                return self.getToken(SimpleCParser.EQ, i)

        def NEQ(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.NEQ)
            else:
                return self.getToken(SimpleCParser.NEQ, i)

        def getRuleIndex(self):
            return SimpleCParser.RULE_equalityExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterEqualityExpression" ):
                listener.enterEqualityExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitEqualityExpression" ):
                listener.exitEqualityExpression(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitEqualityExpression" ):
                return visitor.visitEqualityExpression(self)
            else:
                return visitor.visitChildren(self)




    def equalityExpression(self):

        localctx = SimpleCParser.EqualityExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 74, self.RULE_equalityExpression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 382
            self.relationalExpression()
            self.state = 387
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==38 or _la==39:
                self.state = 383
                _la = self._input.LA(1)
                if not(_la==38 or _la==39):
                    self._errHandler.recoverInline(self)
                else:
                    self._errHandler.reportMatch(self)
                    self.consume()
                self.state = 384
                self.relationalExpression()
                self.state = 389
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class RelationalExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def shiftExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(SimpleCParser.ShiftExpressionContext)
            else:
                return self.getTypedRuleContext(SimpleCParser.ShiftExpressionContext,i)


        def LT(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.LT)
            else:
                return self.getToken(SimpleCParser.LT, i)

        def LTE(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.LTE)
            else:
                return self.getToken(SimpleCParser.LTE, i)

        def GT(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.GT)
            else:
                return self.getToken(SimpleCParser.GT, i)

        def GTE(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.GTE)
            else:
                return self.getToken(SimpleCParser.GTE, i)

        def getRuleIndex(self):
            return SimpleCParser.RULE_relationalExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterRelationalExpression" ):
                listener.enterRelationalExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitRelationalExpression" ):
                listener.exitRelationalExpression(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitRelationalExpression" ):
                return visitor.visitRelationalExpression(self)
            else:
                return visitor.visitChildren(self)




    def relationalExpression(self):

        localctx = SimpleCParser.RelationalExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 76, self.RULE_relationalExpression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 390
            self.shiftExpression()
            self.state = 395
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while (((_la) & ~0x3f) == 0 and ((1 << _la) & 27024896299106304) != 0):
                self.state = 391
                _la = self._input.LA(1)
                if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 27024896299106304) != 0)):
                    self._errHandler.recoverInline(self)
                else:
                    self._errHandler.reportMatch(self)
                    self.consume()
                self.state = 392
                self.shiftExpression()
                self.state = 397
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ShiftExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def additiveExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(SimpleCParser.AdditiveExpressionContext)
            else:
                return self.getTypedRuleContext(SimpleCParser.AdditiveExpressionContext,i)


        def LSHIFT(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.LSHIFT)
            else:
                return self.getToken(SimpleCParser.LSHIFT, i)

        def RSHIFT(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.RSHIFT)
            else:
                return self.getToken(SimpleCParser.RSHIFT, i)

        def getRuleIndex(self):
            return SimpleCParser.RULE_shiftExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterShiftExpression" ):
                listener.enterShiftExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitShiftExpression" ):
                listener.exitShiftExpression(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitShiftExpression" ):
                return visitor.visitShiftExpression(self)
            else:
                return visitor.visitChildren(self)




    def shiftExpression(self):

        localctx = SimpleCParser.ShiftExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 78, self.RULE_shiftExpression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 398
            self.additiveExpression()
            self.state = 403
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==36 or _la==37:
                self.state = 399
                _la = self._input.LA(1)
                if not(_la==36 or _la==37):
                    self._errHandler.recoverInline(self)
                else:
                    self._errHandler.reportMatch(self)
                    self.consume()
                self.state = 400
                self.additiveExpression()
                self.state = 405
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class AdditiveExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def multiplicativeExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(SimpleCParser.MultiplicativeExpressionContext)
            else:
                return self.getTypedRuleContext(SimpleCParser.MultiplicativeExpressionContext,i)


        def PLUS(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.PLUS)
            else:
                return self.getToken(SimpleCParser.PLUS, i)

        def MINUS(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.MINUS)
            else:
                return self.getToken(SimpleCParser.MINUS, i)

        def getRuleIndex(self):
            return SimpleCParser.RULE_additiveExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterAdditiveExpression" ):
                listener.enterAdditiveExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitAdditiveExpression" ):
                listener.exitAdditiveExpression(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAdditiveExpression" ):
                return visitor.visitAdditiveExpression(self)
            else:
                return visitor.visitChildren(self)




    def additiveExpression(self):

        localctx = SimpleCParser.AdditiveExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 80, self.RULE_additiveExpression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 406
            self.multiplicativeExpression()
            self.state = 411
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==48 or _la==49:
                self.state = 407
                _la = self._input.LA(1)
                if not(_la==48 or _la==49):
                    self._errHandler.recoverInline(self)
                else:
                    self._errHandler.reportMatch(self)
                    self.consume()
                self.state = 408
                self.multiplicativeExpression()
                self.state = 413
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class MultiplicativeExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def unaryExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(SimpleCParser.UnaryExpressionContext)
            else:
                return self.getTypedRuleContext(SimpleCParser.UnaryExpressionContext,i)


        def MUL(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.MUL)
            else:
                return self.getToken(SimpleCParser.MUL, i)

        def DIV(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.DIV)
            else:
                return self.getToken(SimpleCParser.DIV, i)

        def MOD(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.MOD)
            else:
                return self.getToken(SimpleCParser.MOD, i)

        def getRuleIndex(self):
            return SimpleCParser.RULE_multiplicativeExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterMultiplicativeExpression" ):
                listener.enterMultiplicativeExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitMultiplicativeExpression" ):
                listener.exitMultiplicativeExpression(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitMultiplicativeExpression" ):
                return visitor.visitMultiplicativeExpression(self)
            else:
                return visitor.visitChildren(self)




    def multiplicativeExpression(self):

        localctx = SimpleCParser.MultiplicativeExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 82, self.RULE_multiplicativeExpression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 414
            self.unaryExpression()
            self.state = 419
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while (((_la) & ~0x3f) == 0 and ((1 << _la) & 7881299347898368) != 0):
                self.state = 415
                _la = self._input.LA(1)
                if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 7881299347898368) != 0)):
                    self._errHandler.recoverInline(self)
                else:
                    self._errHandler.reportMatch(self)
                    self.consume()
                self.state = 416
                self.unaryExpression()
                self.state = 421
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class UnaryExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def postfixExpression(self):
            return self.getTypedRuleContext(SimpleCParser.PostfixExpressionContext,0)


        def unaryExpression(self):
            return self.getTypedRuleContext(SimpleCParser.UnaryExpressionContext,0)


        def INC(self):
            return self.getToken(SimpleCParser.INC, 0)

        def DEC(self):
            return self.getToken(SimpleCParser.DEC, 0)

        def PLUS(self):
            return self.getToken(SimpleCParser.PLUS, 0)

        def MINUS(self):
            return self.getToken(SimpleCParser.MINUS, 0)

        def NOT(self):
            return self.getToken(SimpleCParser.NOT, 0)

        def TILDE(self):
            return self.getToken(SimpleCParser.TILDE, 0)

        def AMP(self):
            return self.getToken(SimpleCParser.AMP, 0)

        def MUL(self):
            return self.getToken(SimpleCParser.MUL, 0)

        def LPAREN(self):
            return self.getToken(SimpleCParser.LPAREN, 0)

        def typeSpecifier(self):
            return self.getTypedRuleContext(SimpleCParser.TypeSpecifierContext,0)


        def RPAREN(self):
            return self.getToken(SimpleCParser.RPAREN, 0)

        def pointer(self):
            return self.getTypedRuleContext(SimpleCParser.PointerContext,0)


        def SIZEOF(self):
            return self.getToken(SimpleCParser.SIZEOF, 0)

        def getRuleIndex(self):
            return SimpleCParser.RULE_unaryExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterUnaryExpression" ):
                listener.enterUnaryExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitUnaryExpression" ):
                listener.exitUnaryExpression(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitUnaryExpression" ):
                return visitor.visitUnaryExpression(self)
            else:
                return visitor.visitChildren(self)




    def unaryExpression(self):

        localctx = SimpleCParser.UnaryExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 84, self.RULE_unaryExpression)
        self._la = 0 # Token type
        try:
            self.state = 444
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,49,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 422
                self.postfixExpression()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 423
                _la = self._input.LA(1)
                if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 38157451580669952) != 0)):
                    self._errHandler.recoverInline(self)
                else:
                    self._errHandler.reportMatch(self)
                    self.consume()
                self.state = 424
                self.unaryExpression()
                pass

            elif la_ == 3:
                self.enterOuterAlt(localctx, 3)
                self.state = 425
                self.match(SimpleCParser.LPAREN)
                self.state = 426
                self.typeSpecifier()
                self.state = 428
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==50:
                    self.state = 427
                    self.pointer()


                self.state = 430
                self.match(SimpleCParser.RPAREN)
                self.state = 431
                self.unaryExpression()
                pass

            elif la_ == 4:
                self.enterOuterAlt(localctx, 4)
                self.state = 433
                self.match(SimpleCParser.SIZEOF)
                self.state = 442
                self._errHandler.sync(self)
                la_ = self._interp.adaptivePredict(self._input,48,self._ctx)
                if la_ == 1:
                    self.state = 434
                    self.match(SimpleCParser.LPAREN)
                    self.state = 435
                    self.typeSpecifier()
                    self.state = 437
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)
                    if _la==50:
                        self.state = 436
                        self.pointer()


                    self.state = 439
                    self.match(SimpleCParser.RPAREN)
                    pass

                elif la_ == 2:
                    self.state = 441
                    self.unaryExpression()
                    pass


                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class PostfixExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def primaryExpression(self):
            return self.getTypedRuleContext(SimpleCParser.PrimaryExpressionContext,0)


        def postfixPart(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(SimpleCParser.PostfixPartContext)
            else:
                return self.getTypedRuleContext(SimpleCParser.PostfixPartContext,i)


        def getRuleIndex(self):
            return SimpleCParser.RULE_postfixExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterPostfixExpression" ):
                listener.enterPostfixExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitPostfixExpression" ):
                listener.exitPostfixExpression(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitPostfixExpression" ):
                return visitor.visitPostfixExpression(self)
            else:
                return visitor.visitChildren(self)




    def postfixExpression(self):

        localctx = SimpleCParser.PostfixExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 86, self.RULE_postfixExpression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 446
            self.primaryExpression()
            self.state = 450
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while ((((_la - 24)) & ~0x3f) == 0 and ((1 << (_la - 24)) & 28724741275651) != 0):
                self.state = 447
                self.postfixPart()
                self.state = 452
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class PostfixPartContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LBRACK(self):
            return self.getToken(SimpleCParser.LBRACK, 0)

        def expression(self):
            return self.getTypedRuleContext(SimpleCParser.ExpressionContext,0)


        def RBRACK(self):
            return self.getToken(SimpleCParser.RBRACK, 0)

        def LPAREN(self):
            return self.getToken(SimpleCParser.LPAREN, 0)

        def RPAREN(self):
            return self.getToken(SimpleCParser.RPAREN, 0)

        def argumentList(self):
            return self.getTypedRuleContext(SimpleCParser.ArgumentListContext,0)


        def DOT(self):
            return self.getToken(SimpleCParser.DOT, 0)

        def IDENTIFIER(self):
            return self.getToken(SimpleCParser.IDENTIFIER, 0)

        def ARROW(self):
            return self.getToken(SimpleCParser.ARROW, 0)

        def INC(self):
            return self.getToken(SimpleCParser.INC, 0)

        def DEC(self):
            return self.getToken(SimpleCParser.DEC, 0)

        def getRuleIndex(self):
            return SimpleCParser.RULE_postfixPart

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterPostfixPart" ):
                listener.enterPostfixPart(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitPostfixPart" ):
                listener.exitPostfixPart(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitPostfixPart" ):
                return visitor.visitPostfixPart(self)
            else:
                return visitor.visitChildren(self)




    def postfixPart(self):

        localctx = SimpleCParser.PostfixPartContext(self, self._ctx, self.state)
        self.enterRule(localctx, 88, self.RULE_postfixPart)
        self._la = 0 # Token type
        try:
            self.state = 468
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [65]:
                self.enterOuterAlt(localctx, 1)
                self.state = 453
                self.match(SimpleCParser.LBRACK)
                self.state = 454
                self.expression()
                self.state = 455
                self.match(SimpleCParser.RBRACK)
                pass
            elif token in [61]:
                self.enterOuterAlt(localctx, 2)
                self.state = 457
                self.match(SimpleCParser.LPAREN)
                self.state = 459
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if ((((_la - 18)) & ~0x3f) == 0 and ((1 << (_la - 18)) & 139620530100633795) != 0):
                    self.state = 458
                    self.argumentList()


                self.state = 461
                self.match(SimpleCParser.RPAREN)
                pass
            elif token in [68]:
                self.enterOuterAlt(localctx, 3)
                self.state = 462
                self.match(SimpleCParser.DOT)
                self.state = 463
                self.match(SimpleCParser.IDENTIFIER)
                pass
            elif token in [67]:
                self.enterOuterAlt(localctx, 4)
                self.state = 464
                self.match(SimpleCParser.ARROW)
                self.state = 465
                self.match(SimpleCParser.IDENTIFIER)
                pass
            elif token in [24]:
                self.enterOuterAlt(localctx, 5)
                self.state = 466
                self.match(SimpleCParser.INC)
                pass
            elif token in [25]:
                self.enterOuterAlt(localctx, 6)
                self.state = 467
                self.match(SimpleCParser.DEC)
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ArgumentListContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def assignmentExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(SimpleCParser.AssignmentExpressionContext)
            else:
                return self.getTypedRuleContext(SimpleCParser.AssignmentExpressionContext,i)


        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.COMMA)
            else:
                return self.getToken(SimpleCParser.COMMA, i)

        def getRuleIndex(self):
            return SimpleCParser.RULE_argumentList

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterArgumentList" ):
                listener.enterArgumentList(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitArgumentList" ):
                listener.exitArgumentList(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitArgumentList" ):
                return visitor.visitArgumentList(self)
            else:
                return visitor.visitChildren(self)




    def argumentList(self):

        localctx = SimpleCParser.ArgumentListContext(self, self._ctx, self.state)
        self.enterRule(localctx, 90, self.RULE_argumentList)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 470
            self.assignmentExpression()
            self.state = 475
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==59:
                self.state = 471
                self.match(SimpleCParser.COMMA)
                self.state = 472
                self.assignmentExpression()
                self.state = 477
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class PrimaryExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def IDENTIFIER(self):
            return self.getToken(SimpleCParser.IDENTIFIER, 0)

        def INTEGER(self):
            return self.getToken(SimpleCParser.INTEGER, 0)

        def FLOAT_LITERAL(self):
            return self.getToken(SimpleCParser.FLOAT_LITERAL, 0)

        def CHAR_LITERAL(self):
            return self.getToken(SimpleCParser.CHAR_LITERAL, 0)

        def STRING_LITERAL(self):
            return self.getToken(SimpleCParser.STRING_LITERAL, 0)

        def NULL(self):
            return self.getToken(SimpleCParser.NULL, 0)

        def LPAREN(self):
            return self.getToken(SimpleCParser.LPAREN, 0)

        def expression(self):
            return self.getTypedRuleContext(SimpleCParser.ExpressionContext,0)


        def RPAREN(self):
            return self.getToken(SimpleCParser.RPAREN, 0)

        def getRuleIndex(self):
            return SimpleCParser.RULE_primaryExpression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterPrimaryExpression" ):
                listener.enterPrimaryExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitPrimaryExpression" ):
                listener.exitPrimaryExpression(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitPrimaryExpression" ):
                return visitor.visitPrimaryExpression(self)
            else:
                return visitor.visitChildren(self)




    def primaryExpression(self):

        localctx = SimpleCParser.PrimaryExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 92, self.RULE_primaryExpression)
        try:
            self.state = 488
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [70]:
                self.enterOuterAlt(localctx, 1)
                self.state = 478
                self.match(SimpleCParser.IDENTIFIER)
                pass
            elif token in [71]:
                self.enterOuterAlt(localctx, 2)
                self.state = 479
                self.match(SimpleCParser.INTEGER)
                pass
            elif token in [72]:
                self.enterOuterAlt(localctx, 3)
                self.state = 480
                self.match(SimpleCParser.FLOAT_LITERAL)
                pass
            elif token in [73]:
                self.enterOuterAlt(localctx, 4)
                self.state = 481
                self.match(SimpleCParser.CHAR_LITERAL)
                pass
            elif token in [74]:
                self.enterOuterAlt(localctx, 5)
                self.state = 482
                self.match(SimpleCParser.STRING_LITERAL)
                pass
            elif token in [19]:
                self.enterOuterAlt(localctx, 6)
                self.state = 483
                self.match(SimpleCParser.NULL)
                pass
            elif token in [61]:
                self.enterOuterAlt(localctx, 7)
                self.state = 484
                self.match(SimpleCParser.LPAREN)
                self.state = 485
                self.expression()
                self.state = 486
                self.match(SimpleCParser.RPAREN)
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class TypeSpecifierContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def CHAR(self):
            return self.getToken(SimpleCParser.CHAR, 0)

        def SHORT(self):
            return self.getToken(SimpleCParser.SHORT, 0)

        def LONG(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.LONG)
            else:
                return self.getToken(SimpleCParser.LONG, i)

        def INT(self):
            return self.getToken(SimpleCParser.INT, 0)

        def SIGNED(self):
            return self.getToken(SimpleCParser.SIGNED, 0)

        def UNSIGNED(self):
            return self.getToken(SimpleCParser.UNSIGNED, 0)

        def FLOAT(self):
            return self.getToken(SimpleCParser.FLOAT, 0)

        def DOUBLE(self):
            return self.getToken(SimpleCParser.DOUBLE, 0)

        def VOID(self):
            return self.getToken(SimpleCParser.VOID, 0)

        def structSpecifier(self):
            return self.getTypedRuleContext(SimpleCParser.StructSpecifierContext,0)


        def getRuleIndex(self):
            return SimpleCParser.RULE_typeSpecifier

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterTypeSpecifier" ):
                listener.enterTypeSpecifier(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitTypeSpecifier" ):
                listener.exitTypeSpecifier(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitTypeSpecifier" ):
                return visitor.visitTypeSpecifier(self)
            else:
                return visitor.visitChildren(self)




    def typeSpecifier(self):

        localctx = SimpleCParser.TypeSpecifierContext(self, self._ctx, self.state)
        self.enterRule(localctx, 94, self.RULE_typeSpecifier)
        self._la = 0 # Token type
        try:
            self.state = 516
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,60,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 491
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==6 or _la==7:
                    self.state = 490
                    _la = self._input.LA(1)
                    if not(_la==6 or _la==7):
                        self._errHandler.recoverInline(self)
                    else:
                        self._errHandler.reportMatch(self)
                        self.consume()


                self.state = 508
                self._errHandler.sync(self)
                la_ = self._interp.adaptivePredict(self._input,59,self._ctx)
                if la_ == 1:
                    self.state = 493
                    self.match(SimpleCParser.CHAR)
                    pass

                elif la_ == 2:
                    self.state = 494
                    self.match(SimpleCParser.SHORT)
                    self.state = 496
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)
                    if _la==1:
                        self.state = 495
                        self.match(SimpleCParser.INT)


                    pass

                elif la_ == 3:
                    self.state = 498
                    self.match(SimpleCParser.LONG)
                    self.state = 499
                    self.match(SimpleCParser.LONG)
                    self.state = 501
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)
                    if _la==1:
                        self.state = 500
                        self.match(SimpleCParser.INT)


                    pass

                elif la_ == 4:
                    self.state = 503
                    self.match(SimpleCParser.LONG)
                    self.state = 505
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)
                    if _la==1:
                        self.state = 504
                        self.match(SimpleCParser.INT)


                    pass

                elif la_ == 5:
                    self.state = 507
                    self.match(SimpleCParser.INT)
                    pass


                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 510
                self.match(SimpleCParser.SIGNED)
                pass

            elif la_ == 3:
                self.enterOuterAlt(localctx, 3)
                self.state = 511
                self.match(SimpleCParser.UNSIGNED)
                pass

            elif la_ == 4:
                self.enterOuterAlt(localctx, 4)
                self.state = 512
                self.match(SimpleCParser.FLOAT)
                pass

            elif la_ == 5:
                self.enterOuterAlt(localctx, 5)
                self.state = 513
                self.match(SimpleCParser.DOUBLE)
                pass

            elif la_ == 6:
                self.enterOuterAlt(localctx, 6)
                self.state = 514
                self.match(SimpleCParser.VOID)
                pass

            elif la_ == 7:
                self.enterOuterAlt(localctx, 7)
                self.state = 515
                self.structSpecifier()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class StructSpecifierContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def STRUCT(self):
            return self.getToken(SimpleCParser.STRUCT, 0)

        def IDENTIFIER(self):
            return self.getToken(SimpleCParser.IDENTIFIER, 0)

        def LBRACE(self):
            return self.getToken(SimpleCParser.LBRACE, 0)

        def RBRACE(self):
            return self.getToken(SimpleCParser.RBRACE, 0)

        def structMemberDeclaration(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(SimpleCParser.StructMemberDeclarationContext)
            else:
                return self.getTypedRuleContext(SimpleCParser.StructMemberDeclarationContext,i)


        def getRuleIndex(self):
            return SimpleCParser.RULE_structSpecifier

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterStructSpecifier" ):
                listener.enterStructSpecifier(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitStructSpecifier" ):
                listener.exitStructSpecifier(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitStructSpecifier" ):
                return visitor.visitStructSpecifier(self)
            else:
                return visitor.visitChildren(self)




    def structSpecifier(self):

        localctx = SimpleCParser.StructSpecifierContext(self, self._ctx, self.state)
        self.enterRule(localctx, 96, self.RULE_structSpecifier)
        self._la = 0 # Token type
        try:
            self.state = 539
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,64,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 518
                self.match(SimpleCParser.STRUCT)
                self.state = 519
                self.match(SimpleCParser.IDENTIFIER)
                self.state = 528
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==63:
                    self.state = 520
                    self.match(SimpleCParser.LBRACE)
                    self.state = 524
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)
                    while (((_la) & ~0x3f) == 0 and ((1 << _la) & 8389630) != 0):
                        self.state = 521
                        self.structMemberDeclaration()
                        self.state = 526
                        self._errHandler.sync(self)
                        _la = self._input.LA(1)

                    self.state = 527
                    self.match(SimpleCParser.RBRACE)


                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 530
                self.match(SimpleCParser.STRUCT)
                self.state = 531
                self.match(SimpleCParser.LBRACE)
                self.state = 535
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while (((_la) & ~0x3f) == 0 and ((1 << _la) & 8389630) != 0):
                    self.state = 532
                    self.structMemberDeclaration()
                    self.state = 537
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)

                self.state = 538
                self.match(SimpleCParser.RBRACE)
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class StructMemberDeclarationContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def typeSpecifier(self):
            return self.getTypedRuleContext(SimpleCParser.TypeSpecifierContext,0)


        def structDeclarator(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(SimpleCParser.StructDeclaratorContext)
            else:
                return self.getTypedRuleContext(SimpleCParser.StructDeclaratorContext,i)


        def SEMI(self):
            return self.getToken(SimpleCParser.SEMI, 0)

        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(SimpleCParser.COMMA)
            else:
                return self.getToken(SimpleCParser.COMMA, i)

        def getRuleIndex(self):
            return SimpleCParser.RULE_structMemberDeclaration

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterStructMemberDeclaration" ):
                listener.enterStructMemberDeclaration(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitStructMemberDeclaration" ):
                listener.exitStructMemberDeclaration(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitStructMemberDeclaration" ):
                return visitor.visitStructMemberDeclaration(self)
            else:
                return visitor.visitChildren(self)




    def structMemberDeclaration(self):

        localctx = SimpleCParser.StructMemberDeclarationContext(self, self._ctx, self.state)
        self.enterRule(localctx, 98, self.RULE_structMemberDeclaration)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 541
            self.typeSpecifier()
            self.state = 542
            self.structDeclarator()
            self.state = 547
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==59:
                self.state = 543
                self.match(SimpleCParser.COMMA)
                self.state = 544
                self.structDeclarator()
                self.state = 549
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 550
            self.match(SimpleCParser.SEMI)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class StructDeclaratorContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def IDENTIFIER(self):
            return self.getToken(SimpleCParser.IDENTIFIER, 0)

        def pointer(self):
            return self.getTypedRuleContext(SimpleCParser.PointerContext,0)


        def arraySuffix(self):
            return self.getTypedRuleContext(SimpleCParser.ArraySuffixContext,0)


        def getRuleIndex(self):
            return SimpleCParser.RULE_structDeclarator

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterStructDeclarator" ):
                listener.enterStructDeclarator(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitStructDeclarator" ):
                listener.exitStructDeclarator(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitStructDeclarator" ):
                return visitor.visitStructDeclarator(self)
            else:
                return visitor.visitChildren(self)




    def structDeclarator(self):

        localctx = SimpleCParser.StructDeclaratorContext(self, self._ctx, self.state)
        self.enterRule(localctx, 100, self.RULE_structDeclarator)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 553
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==50:
                self.state = 552
                self.pointer()


            self.state = 555
            self.match(SimpleCParser.IDENTIFIER)
            self.state = 557
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==65:
                self.state = 556
                self.arraySuffix()


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx





