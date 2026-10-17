// Low/high 32-bit words. These preserve modulo-2^64 arithmetic without shaderInt64.
#pragma once
#define GLSL_U64_HELPERS \
    "uvec2 add64(uvec2 a, uvec2 b) { uint c; uint lo = uaddCarry(a.x,b.x,c); return uvec2(lo,a.y+b.y+c); }\n" \
    "uvec2 sub64(uvec2 a, uvec2 b) { uint c; uint lo = usubBorrow(a.x,b.x,c); return uvec2(lo,a.y-b.y-c); }\n" \
    "uint shf_r(uint hi,uint lo,uint s) { s &= 31u; return s == 0u ? lo : ((lo >> s) | (hi << (32u-s))); }\n" \
    "uint shf_l(uint hi,uint lo,uint s) { s &= 31u; return s == 0u ? hi : ((hi << s) | (lo >> (32u-s))); }\n"
