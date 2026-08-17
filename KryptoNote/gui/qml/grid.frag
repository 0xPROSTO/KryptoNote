#version 440

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    vec2 offset;
    float viewScale;
    float gridSize;
    float gridMain;
    vec2 viewportSize;
    vec4 gridColor;
    vec4 backgroundColor;
};

void main() {
    // ShaderEffect supplies item-local logical coordinates.  Unlike raw
    // window-fragment coordinates, qt_TexCoord0 has the same orientation on OpenGL, Vulkan,
    // software, and Metal backends, and does not require a global Screen DPR.
    vec2 logicalCoord = qt_TexCoord0 * viewportSize;
    vec2 pos = (logicalCoord - offset) / viewScale;

    // Antialiased lines calculation
    vec2 grid = abs(fract(pos / gridSize - 0.5) - 0.5) / fwidth(pos / gridSize);
    float line = min(grid.x, grid.y);
    float gridVal = 1.0 - smoothstep(0.0, 1.0, line);

    vec2 mainGrid = abs(fract(pos / gridMain - 0.5) - 0.5) / fwidth(pos / gridMain);
    float mainLine = min(mainGrid.x, mainGrid.y);
    float mainGridVal = 1.0 - smoothstep(0.0, 1.2, mainLine);

    // Fade out small grid when zooming out
    float subAlpha = smoothstep(0.45, 0.75, viewScale);
    float mainAlpha = smoothstep(0.12, 0.35, viewScale);

    vec4 color = backgroundColor;
    color = mix(color, gridColor, gridVal * 0.22 * subAlpha);
    color = mix(color, gridColor, mainGridVal * 0.52 * mainAlpha);

    fragColor = color * qt_Opacity;
}
