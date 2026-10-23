Shader "Swordsman/SlashArc"
{
    // Procedural additive slash. uv.x = age along the sweep (0 newest), uv.y = rail: 0 hilt side,
    // .78 cutting edge, 1 outer halo; uv.z = per-move intensity.
    // _Spark=1 turns the same material into a soft round particle for impact sparks and flashes.
    Properties
    {
        _Color("Tint",Color)=(1,1,1,1)
        _Intensity("Intensity",Range(0,4))=1.7
        _EdgeWidth("Bright edge width",Range(.01,.3))=.07
        _Streaks("Streak amount",Range(0,1))=.4
        _Spark("Particle mode",Float)=0
    }
    SubShader
    {
        Tags {"Queue"="Transparent" "RenderType"="Transparent" "IgnoreProjector"="True"}
        Blend SrcAlpha One
        ZWrite Off
        Cull Off
        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"
            float _Intensity,_EdgeWidth,_Streaks,_Spark;
            fixed4 _Color;
            struct appdata {float4 vertex:POSITION;float3 uv:TEXCOORD0;fixed4 color:COLOR;};
            struct v2f {float4 pos:SV_POSITION;float3 uv:TEXCOORD0;fixed4 color:COLOR;};
            v2f vert(appdata v)
            {
                v2f o;o.pos=UnityObjectToClipPos(v.vertex);o.uv=v.uv;o.color=v.color*_Color;
                if(o.uv.z<=0)o.uv.z=1; // particles and old meshes carry no intensity
                return o;
            }
            fixed4 frag(v2f i):SV_Target
            {
                if(_Spark>.5)
                {
                    float d=length(i.uv.xy*2-1);
                    float glow=saturate(1-d);glow*=glow;
                    float3 c=lerp(i.color.rgb,1,glow*glow);
                    return fixed4(c*_Intensity,glow*i.color.a);
                }
                float age=i.uv.x,rail=i.uv.y,boost=i.uv.z;
                const float edgeAt=.78;
                float streak=1-_Streaks*(.5+.5*sin(rail*31+age*11));
                float body=pow(saturate(rail/edgeAt),1.5)*.7*streak*step(rail,edgeAt);
                float edge=exp(-pow((rail-edgeAt)/_EdgeWidth,2))*1.9;
                float halo=pow(saturate(1-(rail-edgeAt)/(1-edgeAt)),2)*.5*step(edgeAt,rail);
                float shape=body+edge+halo;
                // Fresh part of the sweep is hot white near the edge, the tail cools into the move colour.
                float heat=saturate(edge*.6*(1-age*1.3));
                float3 c=lerp(i.color.rgb,1,heat);
                float fade=i.color.a*smoothstep(1,.45,age)*smoothstep(0,.05,age+.02);
                return fixed4(c*_Intensity*boost,saturate(shape*fade));
            }
            ENDCG
        }
    }
}
