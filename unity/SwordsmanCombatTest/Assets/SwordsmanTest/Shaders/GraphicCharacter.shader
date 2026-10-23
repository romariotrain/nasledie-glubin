Shader "Swordsman/GraphicCharacter"
{
    Properties
    {
        _MainTex("Painted colour",2D)="white"{}
        _Color("Tint",Color)=(1,1,1,1)
        _BumpMap("Normal",2D)="bump"{}
        _BumpScale("Normal detail",Range(0,1))=.18
        _MetallicGlossMap("Retained data map",2D)="white"{}
        _GlossMapScale("Retained smoothness",Float)=.6
        _Metallic("Retained metalness",Float)=0
        _Glossiness("Retained gloss",Float)=0
        _HeroKeyStrength("Hero key strength",Range(.5,2))=1
        _ShadowLevel("Shadow level",Range(0,1))=.64
        _MidLevel("Midtone level",Range(0,1.5))=.85
        _LitLevel("Lit level",Range(0,1.5))=1
        _BandWidth("Light band softness",Range(.001,.15))=.06
        _RedBoost("Crimson accent",Range(1,2))=1
        _OutlinePixels("Outline pixels",Range(0,3))=0
        _OutlineColor("Outline colour",Color)=(.025,.020,.028,1)
    }
    SubShader
    {
        Tags {"RenderType"="Opaque"}
        Pass
        {
            Name "Thin silhouette"
            Tags {"LightMode"="Always"}
            Cull Front
            ZWrite On
            // Folded coat faces point away from the camera; push the dark hull behind the lit surface
            // so it only shows at the silhouette instead of as black patches.
            Offset 4, 4
            CGPROGRAM
            #pragma vertex outlineVert
            #pragma fragment outlineFrag
            #include "UnityCG.cginc"
            float _OutlinePixels;
            fixed4 _OutlineColor;
            struct outlineInput {float4 vertex:POSITION;float3 normal:NORMAL;};
            float4 outlineVert(outlineInput v):SV_POSITION
            {
                float4 p=UnityObjectToClipPos(v.vertex);
                float3 viewNormal=mul((float3x3)UNITY_MATRIX_V,UnityObjectToWorldNormal(v.normal));
                float2 direction=normalize(viewNormal.xy+float2(.00001,.00001));
                p.xy+=direction*(2*_OutlinePixels/_ScreenParams.xy)*p.w;
                return p;
            }
            fixed4 outlineFrag():SV_Target{return _OutlineColor;}
            ENDCG
        }
        Pass
        {
            Tags {"LightMode"="ForwardBase"}
            // The coat shell folds through itself on wide run strides; draw both sides so no hole opens.
            Cull Off
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_fwdbase
            #include "UnityCG.cginc"
            #include "Lighting.cginc"
            #include "AutoLight.cginc"
            sampler2D _MainTex,_BumpMap;
            float4 _MainTex_ST,_Color;
            float _BumpScale,_HeroKeyStrength,_ShadowLevel,_MidLevel,_LitLevel,_BandWidth,_RedBoost;
            // Globals set by the StylePost test (0 = original look): rim strength and two-tone banding.
            float _StyleRim,_StyleBands;
            struct appdata {float4 vertex:POSITION;float3 normal:NORMAL;float4 tangent:TANGENT;float2 uv:TEXCOORD0;};
            struct v2f {float4 pos:SV_POSITION;float2 uv:TEXCOORD0;float3 n:TEXCOORD1;float3 t:TEXCOORD2;float3 b:TEXCOORD3;SHADOW_COORDS(4)};
            v2f vert(appdata v)
            {
                v2f o;o.pos=UnityObjectToClipPos(v.vertex);o.uv=TRANSFORM_TEX(v.uv,_MainTex);
                o.n=UnityObjectToWorldNormal(v.normal);o.t=UnityObjectToWorldDir(v.tangent.xyz);
                o.b=cross(o.n,o.t)*v.tangent.w*unity_WorldTransformParams.w;
                TRANSFER_SHADOW(o);return o;
            }
            fixed4 frag(v2f i,float facing:VFACE):SV_Target
            {
                float3 detail=UnpackNormal(tex2D(_BumpMap,i.uv));detail.xy*=_BumpScale;
                float3 n=normalize(i.n*detail.z+i.t*detail.x+i.b*detail.y)*(facing>0?1:-1);
                float light=saturate(dot(n,normalize(_WorldSpaceLightPos0.xyz)));
                float width=max(_BandWidth,fwidth(light));
                float bands=_ShadowLevel+(_MidLevel-_ShadowLevel)*smoothstep(.31-width,.31+width,light)+(_LitLevel-_MidLevel)*smoothstep(.71-width,.71+width,light);
                float twoTone=lerp(_ShadowLevel*.92,_LitLevel,smoothstep(.42-width,.42+width,light));
                bands=lerp(bands,twoTone,_StyleBands);
                float shadow=SHADOW_ATTENUATION(i);
                if(_BandWidth<.025)shadow=step(.5,shadow);
                float shade=bands*lerp(.76,1,shadow)*_HeroKeyStrength;
                fixed4 colour=tex2D(_MainTex,i.uv)*_Color;
                float crimson=smoothstep(.004,.04,colour.r-max(colour.g,colour.b))*smoothstep(.70,.95,colour.b/(colour.g+.001));
                colour.rgb*=lerp(1,_RedBoost,crimson);
                colour.rgb*=shade*(.88+.12*_LightColor0.rgb);
                // Cool rim on edges turned away from the camera separates dark cloth from the dark floor.
                float facingView=saturate(dot(n,normalize(UNITY_MATRIX_V[2].xyz)));
                float rim=smoothstep(.62,.8,1-facingView)*_StyleRim;
                colour.rgb+=float3(.42,.5,.68)*rim;
                return fixed4(colour.rgb,1);
            }
            ENDCG
        }
    }
    FallBack "Diffuse"
}
