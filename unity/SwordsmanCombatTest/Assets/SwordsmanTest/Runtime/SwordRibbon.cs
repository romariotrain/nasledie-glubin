using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace SwordsmanTest
{
    // A surface swept by the actual hilt/tip, rather than a thick line at the tip.
    public class SwordRibbon : MonoBehaviour
    {
        public Transform bladeBase, bladeTip;
        public Material material;
        struct Sample { public Vector3 a,b; public float age; }
        readonly List<Sample> samples=new List<Sample>();
        GameObject surface; Mesh mesh;
        public void Tick(float dt,bool emit,Color colour)
        {
            if(!surface)
            {
                surface=new GameObject("Swept sword ribbon");
                mesh=new Mesh{name="Transient sword sweep"};mesh.MarkDynamic();
                surface.AddComponent<MeshFilter>().sharedMesh=mesh;
                var renderer=surface.AddComponent<MeshRenderer>();renderer.sharedMaterial=material;
                renderer.shadowCastingMode=ShadowCastingMode.Off;renderer.receiveShadows=false;
            }
            float lifetime=.105f;
            for(int i=samples.Count-1;i>=0;i--)
            {
                var s=samples[i];s.age+=dt;
                if(s.age>lifetime)samples.RemoveAt(i);else samples[i]=s;
            }
            if(emit && dt>0 && bladeBase && bladeTip)
                samples.Add(new Sample{a=bladeBase.position,b=bladeTip.position});
            if(samples.Count>16)samples.RemoveAt(0);
            mesh.Clear();if(samples.Count<2)return;
            int n=samples.Count;var vertices=new Vector3[n*2];var colours=new Color[n*2];var uv=new Vector2[n*2];var triangles=new int[(n-1)*6];
            for(int i=0;i<n;i++)
            {
                var s=samples[i];float alpha=Mathf.Pow(1-s.age/lifetime,1.3f)*colour.a;
                vertices[2*i]=s.a;vertices[2*i+1]=s.b;
                colours[2*i]=new Color(colour.r,colour.g,colour.b,alpha*.12f);
                colours[2*i+1]=new Color(colour.r,colour.g,colour.b,alpha);
                uv[2*i]=new Vector2(0,0);uv[2*i+1]=new Vector2(1,1);
                if(i<n-1){int k=i*6;triangles[k]=i*2;triangles[k+1]=i*2+1;triangles[k+2]=i*2+2;triangles[k+3]=i*2+1;triangles[k+4]=i*2+3;triangles[k+5]=i*2+2;}
            }
            mesh.vertices=vertices;mesh.colors=colours;mesh.uv=uv;mesh.triangles=triangles;mesh.RecalculateBounds();
        }
        void OnDestroy(){if(mesh)Destroy(mesh);if(surface)Destroy(surface);}
    }
}
