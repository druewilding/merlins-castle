// The air: as in the paintings, things further off fade into a haze, a
// cool, blue one (the far hills and the mountain blue-violet), turning back
// to the haze's own colour where the land meets the sky. (Every material's
// fog, from here: called before any are drawn.) Underground, where the haze
// is dark, so is its blue.

import { ShaderChunk } from "three";

// How much bluer, and how much it's blue, mid-way out.
const BLUE = "vec3(0.8, 0.87, 1.07)";

export function haze() {
  ShaderChunk.fog_fragment = /* glsl */ `
    #ifdef USE_FOG
      #ifdef FOG_EXP2
        float fogFactor = 1.0 - exp( - fogDensity * fogDensity * vFogDepth * vFogDepth );
      #else
        // (Thickening quickly at first, then slowly: easing out.)
        float fogOut = clamp( ( vFogDepth - fogNear ) / ( fogFar - fogNear ), 0.0, 1.0 );
        float fogFactor = 1.0 - ( 1.0 - fogOut ) * ( 1.0 - fogOut );
      #endif
      float fogBlue = smoothstep( 0.0, 0.45, fogFactor ) * ( 1.0 - smoothstep( 0.8, 1.0, fogFactor ) );
      gl_FragColor.rgb = mix( gl_FragColor.rgb, mix( fogColor, fogColor * ${BLUE}, fogBlue ), fogFactor );
    #endif
  `;
}
