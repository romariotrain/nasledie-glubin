Shader "Swordsman/SlashArc"
{
    // Procedural additive slash: uv.x = age along the sweep (0 newest), uv.y = hilt (0) to tip (1).
    // _Spark=1 turns the same material into a soft round particle for impact sparks and flashes.
    Properties
    {
        _Color("Tint",Color)=(1,1,1,1)
        _Intensity("Intensity",Range(0,4))=1.6
        _EdgeWidth("Bright edge width",Range(.02,.5))=.16
        _Streaks("Streak amount",Range(0,1))=.45
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
            struct appdata {float4 vertex:POSITION;float2 uv:TEXCOORD0;fixed4 color:COLOR;};
            struct v2f {float4 pos:SV_POSITION;float2 uv:TEXCOORD0;fixed4 color:COLOR;};
            v2f vert(appdata v){v2f o;o.pos=UnityObjectToClipPos(v.vertex);o.uv=v.uv;o.color=v.color*_Color;return o;}
            fixed4 frag(v2f i):SV_Target
            {
                if(_Spark>.5)
                {
                    float d=length(i.uv*2-1);
                    float glow=saturate(1-d);glow*=glow;
                    float3 c=lerp(i.color.rgb,1,glow*glow);
                    return fixed4(c*_Intensity,glow*i.color.a);
                }
                float age=i.uv.x,height=i.uv.y;
                // Bright cutting edge along the tip path, softer body towards the hilt.
                float edge=smoothstep(1-_EdgeWidth,1,height)*smoothstep(1,.97,height);
                float body=pow(saturate(height),1.8)*.8;
                float streak=1-_Streaks*(.5+.5*sin(height*38+age*9));
                float shape=saturate(body*streak+edge*1.6);
                // Fresh part of the sweep is hot white, the tail cools into the move colour.
                float heat=saturate(edge*(1-age)*1.4);
                float3 c=lerp(i.color.rgb,1,heat);
                float fade=i.color.a*smoothstep(1,.55,age)*smoothstep(0,.04,age+.02);
                return fixed4(c*_Intensity,shape*fade);
            }
            ENDCG
        }
    }
}
