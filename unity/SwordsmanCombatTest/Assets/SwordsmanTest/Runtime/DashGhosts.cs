using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace SwordsmanTest
{
    public class DashGhosts : MonoBehaviour
    {
        public SkinnedMeshRenderer skin;
        public Material material;
        class Ghost{public Mesh mesh;public Matrix4x4 matrix;public float age;}
        readonly List<Ghost> ghosts=new List<Ghost>();
        MaterialPropertyBlock properties;
        void Awake(){properties=new MaterialPropertyBlock();}
        float interval;
        public void Tick(float dt,bool dash)
        {
            interval-=dt;
            if(dash && interval<=0 && skin && dt>0)
            {
                var snapshot=new Mesh{name="Transient dash pose"};skin.BakeMesh(snapshot,true);
                ghosts.Add(new Ghost{mesh=snapshot,matrix=skin.transform.localToWorldMatrix});interval=.055f;
            }
            if(!dash)interval=0;
            for(int i=ghosts.Count-1;i>=0;i--)
            {
                var ghost=ghosts[i];ghost.age+=dt;
                if(ghost.age>.17f){Destroy(ghost.mesh);ghosts.RemoveAt(i);continue;}
                properties.SetColor("_Color",new Color(.48f,.15f,.12f,.22f*(1-ghost.age/.17f)));
                Graphics.DrawMesh(ghost.mesh,ghost.matrix,material,0,null,0,properties,ShadowCastingMode.Off,false);
            }
        }
        void OnDestroy(){foreach(var ghost in ghosts)if(ghost.mesh)Destroy(ghost.mesh);ghosts.Clear();}
    }
}
