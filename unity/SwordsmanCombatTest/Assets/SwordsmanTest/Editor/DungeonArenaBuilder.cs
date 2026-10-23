using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
namespace SwordsmanTest.Editor
{
    // Decorative geometry follows the existing collision layout; combat logic is shared.
    public static class DungeonArenaBuilder
    {
        const string Root="Assets/SwordsmanTest/Art/Dungeon";
        static Material stone,wood,iron,dark,trim,cloth,orange,gold;
        static int serial;
        static readonly System.Random random=new System.Random(7239);
        public static void Apply()
        {
            Directory.CreateDirectory(Root);AssetDatabase.Refresh();serial=0;
            var textureImport=AssetImporter.GetAtPath(Root+"/painted_flagstones_v001.png") as TextureImporter;
            textureImport.wrapMode=TextureWrapMode.Repeat;textureImport.maxTextureSize=2048;
            textureImport.mipmapEnabled=true;textureImport.anisoLevel=8;textureImport.SaveAndReimport();
            var floor=Mat("Painted slate",Color.white);
            floor.mainTexture=AssetDatabase.LoadAssetAtPath<Texture2D>(Root+"/painted_flagstones_v001.png");
            stone=Mat("Masonry",new Color(.78f,.82f,.90f));stone.mainTexture=floor.mainTexture;
            stone.mainTextureScale=Vector2.one/3;stone.mainTextureOffset=new Vector2(1f/3,1f/3);
            wood=Mat("Old oak",Color.white);wood.mainTexture=WoodTexture();wood.EnableKeyword("_EMISSION");
            iron=Mat("Dark iron",new Color(.075f,.08f,.09f),.45f,.18f);
            dark=Mat("Deep joints",new Color(.038f,.045f,.060f));
            trim=Mat("Worn brass",new Color(.38f,.24f,.10f),.45f,.22f);
            cloth=Mat("Burgundy banners",new Color(.22f,.025f,.042f));
            orange=Glow("Flame amber",new Color(1,.28f,.025f));gold=Glow("Flame core",new Color(1,.78f,.23f));
            var oldTiles=GameObject.Find("Floor tiles (visual)");if(oldTiles)oldTiles.SetActive(false);
            var parent=new GameObject("Painted dungeon architecture").transform;
            var floorMesh=new Mesh{name="Painted dungeon floor"};
            floorMesh.vertices=new[]{new Vector3(-9,.018f,-9),new Vector3(9,.018f,-9),new Vector3(9,.018f,9),new Vector3(-9,.018f,9)};
            floorMesh.triangles=new[]{0,2,1,0,3,2};floorMesh.uv=new[]{Vector2.zero,new Vector2(6,0),new Vector2(6,6),new Vector2(0,6)};floorMesh.RecalculateNormals();
            MeshObject("Flagstone floor",floorMesh,floor,parent);
            foreach(var name in new[]{"North collision wall","South collision wall","East collision wall","West collision wall"})
            {
                var go=GameObject.Find(name);if(go)go.GetComponent<Renderer>().enabled=false;
            }
            // The near sides stay low so the camera cannot hide the character behind walls.
            for(int side=0;side<4;side++)
            {
                bool alongX=side<2;float edge=side%2==0?-9:9;
                int rows=edge<0?4:1;
                for(int row=0;row<rows;row++)for(int i=0;i<15;i++)
                {
                    float along=-8.4f+i*1.2f+(row%2==1?.30f:0);
                    if(along>8.65f)continue;
                    Vector3 position=alongX?new Vector3(along,.30f+row*.59f,edge):new Vector3(edge,.30f+row*.59f,along);
                    var size=alongX?new Vector3(1.16f,.55f,.57f):new Vector3(.57f,.55f,1.16f);
                    Box("Wall stone",position,size,stone,parent);
                }
                for(int i=0;i<5;i++)
                {
                    float along=-8.5f+i*4.2f;Vector3 p=alongX?new Vector3(along,0,edge):new Vector3(edge,0,along);
                    Pillar(p,edge<0?2.9f:.8f,parent);
                }
            }
            foreach(var name in new[]{"Dash collision block","Line of sight block"})
            {
                var go=GameObject.Find(name);if(!go)continue;
                go.GetComponent<Renderer>().sharedMaterial=stone;
                Vector3 p=go.transform.position,scale=go.transform.localScale;
                Box("Block coping",p+Vector3.up*(scale.y*.5f+.035f),new Vector3(scale.x+.09f,.10f,scale.z+.09f),stone,parent);
                Box("Block foot",new Vector3(p.x,.09f,p.z),new Vector3(scale.x+.12f,.18f,scale.z+.12f),dark,parent);
            }
            foreach(var dummy in UnityEngine.Object.FindObjectsByType<TrainingDummy>())DressDummy(dummy);
            foreach(var p in new[]{new Vector3(-4.25f,0,-3.6f),new Vector3(4.6f,0,-3.7f),new Vector3(-4.6f,0,4.4f),new Vector3(4.7f,0,4.4f)})Brazier(p,parent);
            Banner(new Vector3(-3.5f,1.65f,-8.65f),Quaternion.identity,parent);
            Banner(new Vector3(4.0f,1.65f,-8.65f),Quaternion.identity,parent);
            Barrel(new Vector3(-6.8f,0,-5.3f),parent);Barrel(new Vector3(-7.4f,0,-4.9f),parent);
            Barrel(new Vector3(6.9f,0,5.8f),parent);
            var key=GameObject.Find("Key light").GetComponent<Light>();
            key.transform.rotation=Quaternion.Euler(52,145,0);key.intensity=.78f;key.color=new Color(.62f,.75f,1);key.shadows=LightShadows.Hard;key.shadowStrength=.85f;
            var fill=GameObject.Find("Soft fill").GetComponent<Light>();fill.intensity=.25f;fill.color=new Color(.48f,.65f,1);
            RenderSettings.ambientSkyColor=new Color(.19f,.25f,.36f);RenderSettings.ambientEquatorColor=new Color(.12f,.16f,.23f);RenderSettings.ambientGroundColor=new Color(.075f,.085f,.12f);
            RenderSettings.fog=false;QualitySettings.pixelLightCount=8;
            var camera=Camera.main;camera.backgroundColor=new Color(.012f,.02f,.035f);
            CharacterReadability();
            var hud=UnityEngine.Object.FindAnyObjectByType<CombatHUD>();if(hud)hud.showPanel=false;
            AssetDatabase.SaveAssets();
        }
        static void CharacterReadability()
        {
            var hero=GameObject.Find("Player_Swordsman");
            string path=Root+"/Hero graphic v002.mat";
            var original=AssetDatabase.LoadAssetAtPath<Material>("Assets/SwordsmanTest/Materials/SwordsmanAtlas.mat");
            var material=AssetDatabase.LoadAssetAtPath<Material>(path);
            if(!material){material=new Material(original);AssetDatabase.CreateAsset(material,path);}
            material.shader=original.shader;material.CopyPropertiesFromMaterial(original);
            material.SetFloat("_HeroKeyStrength",1.16f);material.SetFloat("_ShadowLevel",.51f);
            material.SetFloat("_MidLevel",.82f);material.SetFloat("_LitLevel",1.08f);
            material.SetFloat("_BandWidth",.012f);material.SetFloat("_RedBoost",1.32f);
            material.SetFloat("_OutlinePixels",.85f);material.SetColor("_OutlineColor",new Color(.022f,.018f,.028f));
            EditorUtility.SetDirty(material);
            var steel=Mat("Bright hero blade",new Color(.83f,.90f,.98f),.30f,.32f);
            foreach(var renderer in hero.GetComponentsInChildren<Renderer>())
            {
                if(renderer is TrailRenderer || renderer is LineRenderer)continue;
                renderer.gameObject.layer=8;
                var materials=renderer.sharedMaterials;
                for(int i=0;i<materials.Length;i++)
                {
                    if(materials[i] && materials[i].shader.name=="Swordsman/GraphicCharacter")materials[i]=material;
                    else if(materials[i] && materials[i].name=="SwordSteel")materials[i]=steel;
                }
                renderer.sharedMaterials=materials;
            }
            var light=new GameObject("Hero key (character only)").AddComponent<Light>();
            light.type=LightType.Directional;light.transform.rotation=Quaternion.Euler(43,155,0);
            light.color=new Color(1,.94f,.86f);light.intensity=1.10f;light.cullingMask=1<<8;
            light.shadows=LightShadows.Hard;light.shadowStrength=.85f;light.shadowBias=.03f;
        }
        static void DressDummy(TrainingDummy dummy)
        {
            var body=dummy.body.gameObject;body.transform.localScale=Vector3.one;
            var shape=Lathe(.27f,1.3f,12,.075f);
            body.GetComponent<MeshFilter>().sharedMesh=SaveMesh(shape,"Practice target");body.GetComponent<Renderer>().sharedMaterial=wood;
            dummy.restingTint=Color.white;
            for(int i=0;i<3;i++)Ring("Iron binding",body.transform,new Vector3(0,-.54f+i*.54f,0),.278f,.028f,.055f,iron);
            var post=dummy.transform.Find("Post");post.GetComponent<Renderer>().sharedMaterial=wood;
            var arms=dummy.transform.Find("Target arms");arms.GetComponent<Renderer>().sharedMaterial=wood;
            Box("Target iron base",dummy.transform.position+Vector3.up*.045f,new Vector3(.52f,.09f,.46f),iron,dummy.transform);
            for(int x=-1;x<=1;x+=2)for(int z=-1;z<=1;z+=2)
                Box("Base bolt",dummy.transform.position+new Vector3(x*.19f,.10f,z*.16f),Vector3.one*.055f,trim,dummy.transform);
        }
        static void Pillar(Vector3 p,float height,Transform parent)
        {
            Box("Column plinth",p+Vector3.up*.14f,new Vector3(.92f,.28f,.92f),stone,parent);
            for(int i=0;i<Mathf.CeilToInt(height/.52f);i++)Box("Column block",p+Vector3.up*(.46f+i*.48f),new Vector3(.70f,.45f,.70f),stone,parent);
            Box("Column capital",p+Vector3.up*(height+.17f),new Vector3(.93f,.23f,.93f),stone,parent);
        }
        static void Brazier(Vector3 p,Transform parent)
        {
            var root=new GameObject("Fire brazier");root.transform.SetParent(parent);root.transform.position=p;
            Box("Stone footing",p+Vector3.up*.09f,new Vector3(.65f,.18f,.65f),stone,root.transform);
            Box("Iron stand",p+Vector3.up*.63f,new Vector3(.17f,.98f,.17f),iron,root.transform);
            var bowl=MeshObject("Brazier bowl",Lathe(.34f,.24f,10,.02f),iron,root.transform);bowl.transform.localPosition=Vector3.up*1.18f;
            Ring("Brazier rim",root.transform,Vector3.up*1.29f,.35f,.045f,.09f,iron);
            for(int i=0;i<6;i++)
            {
                float angle=i*Mathf.PI/3;
                var bar=Box("Cage spoke",p+new Vector3(Mathf.Cos(angle)*.31f,1.46f,Mathf.Sin(angle)*.31f),new Vector3(.045f,.40f,.045f),iron,root.transform);
                bar.transform.rotation=Quaternion.Euler(Mathf.Sin(angle)*-16,0,Mathf.Cos(angle)*16);
            }
            var flame=new GameObject("Fire tongues");flame.transform.SetParent(root.transform,false);flame.transform.localPosition=Vector3.up*1.28f;
            var outer=MeshObject("Amber flame",FlameMesh(.23f,.73f),orange,flame.transform);outer.transform.localPosition=Vector3.zero;
            var core=MeshObject("Yellow core",FlameMesh(.13f,.48f),gold,flame.transform);core.transform.localPosition=new Vector3(.02f,.03f,.02f);
            var tongue=MeshObject("Side flame",FlameMesh(.10f,.49f),orange,flame.transform);tongue.transform.localPosition=new Vector3(-.14f,.01f,.05f);tongue.transform.localRotation=Quaternion.Euler(0,30,12);
            var light=new GameObject("Torch light").AddComponent<Light>();light.transform.SetParent(root.transform,false);light.transform.localPosition=Vector3.up*1.65f;
            light.type=LightType.Point;light.color=new Color(1,.48f,.15f);light.range=4.6f;light.intensity=3.0f;light.renderMode=LightRenderMode.ForcePixel;
            light.shadows=LightShadows.None;
            var flicker=root.AddComponent<TorchFlicker>();flicker.fireLight=light;flicker.flame=flame.transform;flicker.intensity=3.0f;flicker.phase=(float)random.NextDouble()*10;
            var collider=root.AddComponent<CapsuleCollider>();collider.center=Vector3.up*.7f;collider.height=1.4f;collider.radius=.30f;
        }
        static void Banner(Vector3 p,Quaternion rotation,Transform parent)
        {
            var go=Box("Hanging burgundy banner",p,new Vector3(.85f,1.8f,.045f),cloth,parent);go.transform.rotation=rotation;
            Box("Banner rod",p+Vector3.up*.96f,new Vector3(1.08f,.065f,.09f),iron,parent);
            Box("Banner gold stripe",p+new Vector3(0,-.68f,.03f),new Vector3(.72f,.045f,.01f),trim,parent);
            var sigil=Box("Banner diamond",p+new Vector3(0,.1f,.035f),new Vector3(.25f,.25f,.02f),trim,parent);sigil.transform.rotation=Quaternion.Euler(0,0,45);
        }
        static void Barrel(Vector3 p,Transform parent)
        {
            var body=MeshObject("Oak barrel",Lathe(.38f,.94f,12,.07f),wood,parent);body.transform.position=p+Vector3.up*.49f;
            Ring("Barrel hoops",body.transform,Vector3.up*.33f,.39f,.035f,.06f,iron);Ring("Barrel hoops",body.transform,Vector3.down*.33f,.39f,.035f,.06f,iron);
        }
        static void Ring(string name,Transform parent,Vector3 p,float radius,float thickness,float height,Material mat)
        {
            var vertices=new List<Vector3>();var triangles=new List<int>();int sides=12;
            for(int layer=0;layer<4;layer++)for(int i=0;i<sides;i++)
            {float a=i*Mathf.PI*2/sides;float r=layer<2?radius:radius-thickness;float y=(layer%2==0?-.5f:.5f)*height;vertices.Add(new Vector3(Mathf.Cos(a)*r,y,Mathf.Sin(a)*r));}
            for(int side=0;side<4;side++)for(int i=0;i<sides;i++)
            {int j=(i+1)%sides;int a=side==0?i:side==1?i+sides:side==2?i+3*sides:i+2*sides;int b=side==0?j:side==1?j+sides:side==2?j+3*sides:j+2*sides;int c=side==0?i+sides:side==1?i+3*sides:side==2?i+2*sides:i;int d=side==0?j+sides:side==1?j+3*sides:side==2?j+2*sides:j;triangles.AddRange(new[]{a,c,b,b,c,d});}
            var mesh=new Mesh{name=name};mesh.SetVertices(vertices);mesh.SetTriangles(triangles,0);mesh.RecalculateNormals();
            var go=MeshObject(name,mesh,mat,parent);go.transform.localPosition=p;
        }
        static Mesh Lathe(float radius,float height,int sides,float bevel)
        {
            var vertices=new List<Vector3>();var uvs=new List<Vector2>();var triangles=new List<int>();
            for(int row=0;row<4;row++)for(int i=0;i<=sides;i++)
            {
                float a=i*Mathf.PI*2/sides;float r=radius-(row==0||row==3?bevel*.45f:0);
                float y=row==0?-height/2:row==1?-height/2+bevel:row==2?height/2-bevel:height/2;
                vertices.Add(new Vector3(Mathf.Cos(a)*r,y,Mathf.Sin(a)*r));uvs.Add(new Vector2((float)i/sides,(y+height/2)/height));
            }
            for(int row=0;row<3;row++)for(int i=0;i<sides;i++){int k=row*(sides+1)+i;triangles.AddRange(new[]{k,k+sides+1,k+1,k+1,k+sides+1,k+sides+2});}
            for(int cap=0;cap<2;cap++)
            {
                int c=vertices.Count;vertices.Add(new Vector3(0,(cap==0?-.5f:.5f)*height,0));uvs.Add(new Vector2(.5f,.5f));
                int start=cap==0?0:3*(sides+1);for(int i=0;i<sides;i++)triangles.AddRange(cap==0?new[]{c,start+i,start+i+1}:new[]{c,start+i+1,start+i});
            }
            var mesh=new Mesh();mesh.SetVertices(vertices);mesh.SetUVs(0,uvs);mesh.SetTriangles(triangles,0);mesh.RecalculateNormals();return mesh;
        }
        static Mesh FlameMesh(float radius,float height)
        {
            var mesh=Lathe(radius,height,7,.12f);var v=mesh.vertices;
            for(int i=0;i<v.Length;i++){float t=(v[i].y+height/2)/height;float s=Mathf.Sin(t*Mathf.PI)*(.8f+.2f*t);v[i].x=v[i].x*s+Mathf.Sin(t*5)*.075f;v[i].z*=s;v[i].y+=height/2;}
            mesh.vertices=v;mesh.RecalculateNormals();return mesh;
        }
        static GameObject Box(string name,Vector3 p,Vector3 size,Material mat,Transform parent)
        {
            var go=GameObject.CreatePrimitive(PrimitiveType.Cube);go.name=name;go.transform.SetParent(parent);go.transform.position=p;go.transform.localScale=size;
            UnityEngine.Object.DestroyImmediate(go.GetComponent<Collider>());go.GetComponent<Renderer>().sharedMaterial=mat;return go;
        }
        static GameObject MeshObject(string name,Mesh mesh,Material mat,Transform parent)
        {
            var go=new GameObject(name);go.transform.SetParent(parent,false);go.AddComponent<MeshFilter>().sharedMesh=SaveMesh(mesh,name);
            go.AddComponent<MeshRenderer>().sharedMaterial=mat;return go;
        }
        static Mesh SaveMesh(Mesh mesh,string name)
        {
            string path=Root+"/mesh_"+(serial++).ToString("D3")+".asset";mesh.name=name;
            var old=AssetDatabase.LoadAssetAtPath<Mesh>(path);
            if(old){EditorUtility.CopySerialized(mesh,old);UnityEngine.Object.DestroyImmediate(mesh);EditorUtility.SetDirty(old);return old;}
            AssetDatabase.CreateAsset(mesh,path);return mesh;
        }
        static Material Mat(string name,Color colour,float metal=0,float gloss=.04f)
        {
            string path=Root+"/"+name+".mat";var mat=AssetDatabase.LoadAssetAtPath<Material>(path);
            if(!mat){mat=new Material(Shader.Find("Standard"));AssetDatabase.CreateAsset(mat,path);}
            mat.color=colour;mat.SetFloat("_Metallic",metal);mat.SetFloat("_Glossiness",gloss);EditorUtility.SetDirty(mat);return mat;
        }
        static Material Glow(string name,Color colour)
        {
            var mat=Mat(name,colour);mat.shader=Shader.Find("Unlit/Color");mat.color=colour;EditorUtility.SetDirty(mat);return mat;
        }
        static Texture2D WoodTexture()
        {
            int n=512;var texture=new Texture2D(n,n,TextureFormat.RGB24,true);var pixels=new Color[n*n];
            for(int y=0;y<n;y++)for(int x=0;x<n;x++)
            {
                float warp=Mathf.PerlinNoise(x*.018f,y*.008f)*3;float grain=Mathf.PerlinNoise(x*.18f+warp,y*.009f);
                float plank=(x%64<2)?.42f:1;float scratch=grain<.36f?.70f:1;
                float value=(.84f+.22f*Mathf.PerlinNoise(x*.025f,y*.018f))*plank*scratch;
                pixels[y*n+x]=new Color(.42f,.235f,.105f)*value;
            }
            texture.SetPixels(pixels);texture.Apply();string path=Root+"/painted_oak_v001.png";File.WriteAllBytes(path,texture.EncodeToPNG());UnityEngine.Object.DestroyImmediate(texture);AssetDatabase.ImportAsset(path);
            var importer=(TextureImporter)AssetImporter.GetAtPath(path);importer.wrapMode=TextureWrapMode.Repeat;importer.maxTextureSize=512;importer.SaveAndReimport();return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
        }
    }
}
