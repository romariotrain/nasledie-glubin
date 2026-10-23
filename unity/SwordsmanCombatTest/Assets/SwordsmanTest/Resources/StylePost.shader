Shader "Hidden/Swordsman/StylePost"
{
    // Pass 0: ink outline from the camera depth+normals texture, at the resolution of _MainTex.
    // Pass 1: plain point-filtered copy (used for the low-resolution upscale).
    Properties { _MainTex("Source",2D)="white"{} }
    SubShader
    {
        ZTest Always Cull Off ZWrite Off
        CGINCLUDE
        #include "UnityCG.cginc"
        sampler2D _MainTex; float4 _MainTex_TexelSize;
        sampler2D _CameraDepthNormalsTexture;
        float _OutlineWidth,_DepthEdge,_NormalEdge;
        fixed4 _InkColor;
        struct v2f {float4 pos:SV_POSITION;float2 uv:TEXCOORD0;};
        v2f vert(appdata_img v){v2f o;o.pos=UnityObjectToClipPos(v.vertex);o.uv=v.texcoord;return o;}
        void Sample(float2 uv,out float depth,out float3 normal)
        {
            DecodeDepthNormal(tex2D(_CameraDepthNormalsTexture,uv),depth,normal);
            depth*=_ProjectionParams.z; // metres along the view axis
        }
        ENDCG
        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            fixed4 frag(v2f i):SV_Target
            {
                fixed4 colour=tex2D(_MainTex,i.uv);
                float2 d=_MainTex_TexelSize.xy*_OutlineWidth;
                float dc;float3 nc;Sample(i.uv,dc,nc);
                float edge=0;
                // Compare with four neighbours: a step in depth draws the silhouette, a fold in normals the inner lines.
                float2 offsets[4]={float2(d.x,0),float2(-d.x,0),float2(0,d.y),float2(0,-d.y)};
                for(int k=0;k<4;k++)
                {
                    float dn;float3 nn;Sample(i.uv+offsets[k],dn,nn);
                    // Only the nearer side inks, so silhouettes stay one pixel and sit on the character.
                    float silhouette=step(_DepthEdge,dn-dc);
                    float crease=step(dot(nc,nn),_NormalEdge)*step(abs(dn-dc),_DepthEdge*2);
                    edge=max(edge,max(silhouette,crease));
                }
                // The far background (empty sky) never inks.
                edge*=step(dc,_ProjectionParams.z*.99);
                return lerp(colour,_InkColor,edge*_InkColor.a);
            }
            ENDCG
        }
        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            fixed4 frag(v2f i):SV_Target{return tex2D(_MainTex,i.uv);}
            ENDCG
        }
    }
}
