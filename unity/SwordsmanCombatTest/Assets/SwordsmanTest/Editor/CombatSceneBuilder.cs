using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace SwordsmanTest.Editor
{
    public static class CombatSceneBuilder
    {
        const string Base = "Assets/SwordsmanTest";
        const string Fbx = Base + "/Art/SK_Swordsman_Combat_v010.fbx";
        static bool dungeonStyle;
        static string ScenePath => Base + (dungeonStyle ? "/Scenes/DungeonCombatTest.unity" : "/Scenes/CombatTest.unity");
        static string Repo => Path.GetFullPath(Path.Combine(Application.dataPath, "../../.."));
        static string Reports => Path.Combine(Repo, dungeonStyle ? "work/unity-dungeon-test" : "work/unity-test");
        [Serializable] class ImportReport
        {
            public string unity, sourceFbxSha256, scene, buildResult;
            public int triangles, bones, clips;
            public float modelHeight, animationBoundsHeight;
            public bool avatarValid;
            public string[] animationNames;
            public float[] animationLengths;
            public Vector3 detectedForwardBeforeCorrection;
        }
        [Serializable] class Phases
        {
            public float[] startup, active, recovery, input_buffer, dodge_cancel_suggested;
            public float[] movement_window, invulnerability_suggested;
        }
        [Serializable] class EventClips
        {
            public Phases attack_1, attack_2, attack_3, dodge, piercing_lunge;
        }
        [Serializable] class Events { public EventClips clips; public float run_reference_speed_m_s; }
        static readonly string[] Names = {"idle","run","attack_1","attack_2","attack_3","dodge","piercing_lunge","hurt","death"};

        [MenuItem("Swordsman Test/Rebuild test scene")]
        public static void Setup()
        {
            Directory.CreateDirectory(Reports);
            foreach (var folder in new[] {"Scenes","Materials","Data","Prefabs"})
                Directory.CreateDirectory(Base + "/" + folder);
            AssetDatabase.Refresh();
            ConfigureImport();
            var imported = AssetDatabase.LoadAssetAtPath<GameObject>(Fbx);
            if (!imported) throw new Exception("FBX did not import");
            var clips = AssetDatabase.LoadAllAssetsAtPath(Fbx).OfType<AnimationClip>()
                .Where(c => !c.name.StartsWith("__preview__", StringComparison.Ordinal)).ToArray();
            if (clips.Length != 9 || Names.Except(clips.Select(c => c.name)).Any())
                throw new Exception("Expected exactly nine named clips, got: " + string.Join(",", clips.Select(c => c.name)));
            var config = MakeTuning();
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var stone = Material("Stone", new Color(.18f,.21f,.24f));
            var grout = Material("Grout", new Color(.07f,.09f,.11f));
            var edge = Material("Wall", new Color(.12f,.15f,.19f));
            var wood = Material("Wood", new Color(.28f,.13f,.055f));
            var targetMaterial = Material("Target", new Color(.64f,.32f,.16f));
            var steel = Material("SwordSteel", new Color(.55f,.62f,.68f), .7f, .45f);
            var leather = Material("SwordGrip", new Color(.10f,.055f,.025f));
            var bronze = Material("SwordGuard", new Color(.45f,.25f,.06f), .65f, .4f);
            var atlas = CharacterMaterial();
            Cube("Ground", new Vector3(0,-.15f,0), new Vector3(18,.3f,18), grout);
            var tiles = new GameObject("Floor tiles (visual)");
            for (int x=-9;x<9;x++) for(int z=-9;z<9;z++)
            {
                var tile=Cube("Tile",new Vector3(x+.5f,-.01f,z+.5f),new Vector3(.97f,.05f,.97f),stone,false);
                tile.transform.SetParent(tiles.transform);
            }
            var tileMeshes=tiles.GetComponentsInChildren<MeshFilter>();
            var combined=new Mesh{name="Arena tiles"};
            combined.CombineMeshes(tileMeshes.Select(f=>new CombineInstance{mesh=f.sharedMesh,transform=f.transform.localToWorldMatrix}).ToArray());
            string floorPath=Base+"/Art/ArenaTiles.asset";
            var savedFloor=AssetDatabase.LoadAssetAtPath<Mesh>(floorPath);
            if(savedFloor){EditorUtility.CopySerialized(combined,savedFloor);UnityEngine.Object.DestroyImmediate(combined);EditorUtility.SetDirty(savedFloor);}
            else{AssetDatabase.CreateAsset(combined,floorPath);savedFloor=combined;}
            foreach(var filter in tileMeshes)UnityEngine.Object.DestroyImmediate(filter.gameObject);
            tiles.AddComponent<MeshFilter>().sharedMesh=savedFloor;
            tiles.AddComponent<MeshRenderer>().sharedMaterial=stone;
            Cube("North collision wall",new Vector3(0,.55f,9),new Vector3(18,1.1f,.4f),edge);
            Cube("South collision wall",new Vector3(0,.55f,-9),new Vector3(18,1.1f,.4f),edge);
            Cube("East collision wall",new Vector3(9,.55f,0),new Vector3(.4f,1.1f,18),edge);
            Cube("West collision wall",new Vector3(-9,.55f,0),new Vector3(.4f,1.1f,18),edge);
            Cube("Dash collision block",new Vector3(-2.7f,.5f,3.6f),Vector3.one,wood);
            Cube("Line of sight block",new Vector3(4.8f,.7f,1.5f),new Vector3(1.2f,1.4f,1.2f),edge);
            var targets = new List<TrainingDummy>();
            foreach(var position in new[]{new Vector3(0,0,0),new Vector3(0,0,2),new Vector3(-3,0,.5f),new Vector3(3,0,0),new Vector3(3,0,3.5f)})
                targets.Add(Dummy(position,targetMaterial,wood));

            var hero = new GameObject("Player_Swordsman"); hero.transform.position = new Vector3(0,.025f,-2.2f);
            var motor=hero.AddComponent<CharacterController>(); motor.height=1.8f; motor.radius=.28f;
            motor.center=new Vector3(0,.9f,0); motor.skinWidth=.025f; motor.stepOffset=.18f; motor.minMoveDistance=0;
            var anchor=new GameObject("VisualOrientation"); anchor.transform.SetParent(hero.transform,false);
            var model=(GameObject)PrefabUtility.InstantiatePrefab(imported,anchor.transform);
            model.name="SwordsmanVisual"; model.transform.localPosition=Vector3.zero;
            foreach(var renderer in model.GetComponentsInChildren<Renderer>())
            {
                var materials=renderer.sharedMaterials;
                for(int i=0;i<materials.Length;i++)
                {
                    string name=materials[i] ? materials[i].name.ToLowerInvariant() : "";
                    materials[i]=name.Contains("steel") ? steel : name.Contains("guard") ? bronze : name.Contains("grip") ? leather : atlas;
                }
                renderer.sharedMaterials=materials;
            }
            Vector3 detected = Vector3.zero;
            foreach(string side in new[]{"L","R"})
                detected += Find(model.transform,"Toe."+side).position - Find(model.transform,"Foot."+side).position;
            detected=Vector3.ProjectOnPlane(detected,Vector3.up).normalized;
            anchor.transform.localRotation=Quaternion.FromToRotation(detected,Vector3.forward);
            var animator=model.GetComponentInChildren<Animator>();
            if(!animator || !animator.avatar || !animator.avatar.isValid) throw new Exception("Generic avatar is invalid");
            animator.applyRootMotion=false;
            var playback=hero.AddComponent<CombatAnimation>(); playback.animator=animator;
            playback.clips=Names.Select(n=>clips.Single(c=>c.name==n)).ToArray();
            var player=hero.AddComponent<CombatPlayer>(); player.motor=motor; player.animationPlayer=playback;
            player.tuning=config; player.targets=targets.ToArray();player.showHitboxes=false;
            var trailObject=new GameObject("Blade trail");
            var sword=Find(model.transform,"SM_Longsword");
            if(!sword) sword=model.GetComponentsInChildren<MeshFilter>().First(m=>m.name.Contains("Longsword")).transform;
            trailObject.transform.SetParent(sword,false);
            var mesh=sword.GetComponent<MeshFilter>().sharedMesh;
            var bounds=mesh.bounds; int axis=bounds.size.x>bounds.size.y ? 0 : 1; if(bounds.size.z>bounds.size[axis]) axis=2;
            Vector3 tip=bounds.center; tip[axis]=bounds.max[axis]; trailObject.transform.localPosition=tip;
            var trail=trailObject.AddComponent<TrailRenderer>(); trail.time=.07f; trail.startWidth=.04f; trail.endWidth=0;
            trail.minVertexDistance=.025f; trail.emitting=false; trail.shadowCastingMode=ShadowCastingMode.Off;
            trail.material=UnlitMaterial("Trail",new Color(1,.65f,.2f,.7f)); player.bladeTrail=trail;
            var baseObject=new GameObject("Blade ribbon base");baseObject.transform.SetParent(sword,false);
            Vector3 hilt=bounds.center;hilt[axis]=Mathf.Lerp(bounds.min[axis],bounds.max[axis],.16f);baseObject.transform.localPosition=hilt;
            var ribbon=hero.AddComponent<SwordRibbon>();ribbon.bladeBase=baseObject.transform;ribbon.bladeTip=trailObject.transform;
            ribbon.material=UnlitMaterial("Broad sword sweep",Color.white);player.swordRibbon=ribbon;
            var ghosts=hero.AddComponent<DashGhosts>();ghosts.skin=model.GetComponentInChildren<SkinnedMeshRenderer>();
            ghosts.material=UnlitMaterial("Dash ghosts",Color.white);player.dashGhosts=ghosts;
            var line=new GameObject("Hit area").AddComponent<LineRenderer>(); line.useWorldSpace=true;
            line.widthMultiplier=.025f; line.material=UnlitMaterial("Hitbox",Color.white); line.enabled=false;
            player.hitboxOutline=line;
            var cameraObject=new GameObject("Main Camera"); cameraObject.tag="MainCamera";
            var camera=cameraObject.AddComponent<Camera>(); camera.orthographic=true; camera.orthographicSize=3.6f;
            camera.nearClipPlane=.1f; camera.farClipPlane=100; camera.backgroundColor=new Color(.055f,.07f,.095f);
            camera.clearFlags=CameraClearFlags.SolidColor;
            cameraObject.AddComponent<AudioListener>();
            var follow=cameraObject.AddComponent<CombatCamera>(); follow.target=hero.transform; follow.Snap();
            player.gameCamera=camera; player.cameraRig=follow;
            var hud=new GameObject("Combat HUD").AddComponent<CombatHUD>(); hud.player=player;
            var smoke=new GameObject("Runtime validation").AddComponent<CombatSmokeTest>(); smoke.player=player;
            var key=new GameObject("Key light").AddComponent<Light>(); key.type=LightType.Directional;
            key.transform.rotation=Quaternion.Euler(50,145,0); key.intensity=1.25f; key.color=new Color(1,.88f,.73f);
            key.shadows=LightShadows.Soft;
            var fill=new GameObject("Soft fill").AddComponent<Light>();fill.type=LightType.Directional;
            fill.transform.rotation=Quaternion.Euler(55,-35,0);fill.intensity=.7f;fill.color=new Color(.67f,.78f,1);
            fill.shadows=LightShadows.None;
            RenderSettings.ambientMode=AmbientMode.Trilight;
            RenderSettings.ambientSkyColor=new Color(.38f,.44f,.56f);
            RenderSettings.ambientEquatorColor=new Color(.25f,.28f,.33f);
            RenderSettings.ambientGroundColor=new Color(.16f,.15f,.14f);
            QualitySettings.shadowDistance=45; QualitySettings.shadows=ShadowQuality.All;
            QualitySettings.shadowResolution=ShadowResolution.High; QualitySettings.antiAliasing=4;
            QualitySettings.vSyncCount=1;
            PlayerSettings.colorSpace=ColorSpace.Linear; PlayerSettings.runInBackground=true;
            PlayerSettings.productName="Swordsman Combat Test";
            PlayerSettings.defaultScreenWidth=1280; PlayerSettings.defaultScreenHeight=800;
            PlayerSettings.fullScreenMode=FullScreenMode.Windowed; PlayerSettings.resizableWindow=true;
            PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone, ScriptingImplementation.Mono2x);
            if(dungeonStyle)DungeonArenaBuilder.Apply();
            var renderers=model.GetComponentsInChildren<Renderer>();
            Bounds total=renderers[0].bounds; foreach(var renderer in renderers) total.Encapsulate(renderer.bounds);
            Bounds geometry=new Bounds();bool hasGeometry=false;
            void Include(Vector3 point){if(!hasGeometry){geometry=new Bounds(point,Vector3.zero);hasGeometry=true;}else geometry.Encapsulate(point);}
            foreach(var skin in model.GetComponentsInChildren<SkinnedMeshRenderer>())
            {
                var baked=new Mesh();skin.BakeMesh(baked,true);
                foreach(var vertex in baked.vertices)Include(skin.transform.TransformPoint(vertex));
                UnityEngine.Object.DestroyImmediate(baked);
            }
            foreach(var filter in model.GetComponentsInChildren<MeshFilter>())
                foreach(var vertex in filter.sharedMesh.vertices)Include(filter.transform.TransformPoint(vertex));
            if(geometry.size.y<1.5f || geometry.size.y>2.1f) throw new Exception("Unexpected actual geometry height "+geometry.size.y);
            int triangles=model.GetComponentsInChildren<MeshFilter>().Sum(f=>f.sharedMesh.triangles.Length/3)
                +model.GetComponentsInChildren<SkinnedMeshRenderer>().Sum(r=>r.sharedMesh.triangles.Length/3);
            if(triangles!=11980) throw new Exception("Triangle mismatch "+triangles);
            var report=new ImportReport{unity=Application.unityVersion,sourceFbxSha256=Hash(Fbx),triangles=triangles,
                bones=model.GetComponentsInChildren<SkinnedMeshRenderer>().Sum(r=>r.bones.Length),clips=clips.Length,
                modelHeight=geometry.size.y,animationBoundsHeight=total.size.y,avatarValid=animator.avatar.isValid,scene=ScenePath,
                animationNames=clips.Select(c=>c.name).ToArray(),animationLengths=clips.Select(c=>c.length).ToArray(),
                detectedForwardBeforeCorrection=detected};
            File.WriteAllText(Path.Combine(Reports,"unity-import-report.json"),JsonUtility.ToJson(report,true));
            PrefabUtility.SaveAsPrefabAsset(hero,Base+"/Prefabs/SwordsmanPlayer_v010.prefab");
            EditorSceneManager.SaveScene(UnityEngine.SceneManagement.SceneManager.GetActiveScene(),ScenePath);
            EditorBuildSettings.scenes=new[]{new EditorBuildSettingsScene(ScenePath,true)};
            AssetDatabase.SaveAssets();
            Debug.Log("SWORDSMAN_SCENE_READY "+ScenePath);
        }

        public static void Build()
        {
            try
            {
                Setup();
                string path=Path.Combine(Reports,"Build/SwordsmanCombatTest.exe"); Directory.CreateDirectory(Path.GetDirectoryName(path));
                var result=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{ScenePath},locationPathName=path,
                    target=BuildTarget.StandaloneWindows64,options=BuildOptions.Development});
                File.WriteAllText(Path.Combine(Reports,"build-result.json"),JsonUtility.ToJson(new BuildResultInfo{
                    result=result.summary.result.ToString(),errors=(int)result.summary.totalErrors,
                    warnings=(int)result.summary.totalWarnings,bytes=(long)result.summary.totalSize},true));
                if(result.summary.result!=BuildResult.Succeeded) throw new Exception("Build failed");
                Debug.Log("SWORDSMAN_BUILD_READY "+path);
                if(Application.isBatchMode) EditorApplication.Exit(0);
            }
            catch(Exception exception) { Debug.LogException(exception); if(Application.isBatchMode) EditorApplication.Exit(1); else throw; }
        }
        [MenuItem("Swordsman Test/Create painted dungeon scene")]
        public static void SetupDungeon(){dungeonStyle=true;try{Setup();}finally{dungeonStyle=false;}}
        public static void BuildDungeon(){dungeonStyle=true;try{Build();}finally{dungeonStyle=false;}}
        [Serializable] class BuildResultInfo { public string result; public int errors,warnings; public long bytes; }

        static void ConfigureImport()
        {
            var importer=AssetImporter.GetAtPath(Fbx) as ModelImporter;
            if(!importer) throw new Exception("Missing FBX ModelImporter");
            importer.animationType=ModelImporterAnimationType.Generic;
            importer.avatarSetup=ModelImporterAvatarSetup.CreateFromThisModel;
            importer.motionNodeName="Root"; importer.optimizeGameObjects=false;
            importer.importAnimation=true; importer.animationCompression=ModelImporterAnimationCompression.Off;
            importer.bakeAxisConversion=true; importer.importCameras=false; importer.importLights=false;
            importer.importBlendShapes=false; importer.SaveAndReimport();
            var takes=importer.defaultClipAnimations;
            foreach(var clip in takes)
            {
                string name=Names.FirstOrDefault(n=>clip.name==n || clip.name.EndsWith("|"+n,StringComparison.Ordinal));
                if(name==null) throw new Exception("Unexpected FBX take "+clip.name);
                clip.name=name; clip.loopTime=name=="idle"||name=="run"; clip.loopPose=false;
                clip.lockRootRotation=true; clip.lockRootPositionXZ=true;
                clip.keepOriginalPositionY=true; clip.keepOriginalPositionXZ=true; clip.keepOriginalOrientation=true;
            }
            importer.clipAnimations=takes; importer.SaveAndReimport();
        }
        static CombatTuning MakeTuning()
        {
            var config=AssetDatabase.LoadAssetAtPath<CombatTuning>(Base+"/Data/CombatTuning_v010.asset");
            if(!config){config=ScriptableObject.CreateInstance<CombatTuning>();AssetDatabase.CreateAsset(config,Base+"/Data/CombatTuning_v010.asset");}
            config.runSpeed=4.3f;
            var events=JsonUtility.FromJson<Events>(File.ReadAllText(Base+"/Art/combat_events.json"));
            MoveDefinition Strike(string id,Phases phase,float damage,float reach,float arc,float push,float stop)
                =>new MoveDefinition{id=id,duration=phase.recovery[1],activeStart=phase.active[0],activeEnd=phase.active[1],
                    bufferStart=phase.input_buffer!=null?phase.input_buffer[0]:0,cancelStart=phase.dodge_cancel_suggested[0],
                    damage=damage,reach=reach,arc=arc,knockback=push,hitstop=stop};
            config.runReferenceSpeed=events.run_reference_speed_m_s;
            var dodge=events.clips.dodge; var lunge=events.clips.piercing_lunge;
            config.moves=new[]{Strike("attack_1",events.clips.attack_1,20,1.65f,130,.08f,.015f),
                Strike("attack_2",events.clips.attack_2,25,1.7f,160,.12f,.02f),
                Strike("attack_3",events.clips.attack_3,45,1.9f,110,.85f,.055f),
                new MoveDefinition{id="dodge",duration=10f/30,travelDistance=3,travelStart=dodge.movement_window[0],travelEnd=dodge.movement_window[1],
                    invulnerableStart=dodge.invulnerability_suggested[0],invulnerableEnd=dodge.invulnerability_suggested[1]},
                new MoveDefinition{id="piercing_lunge",duration=lunge.recovery[1],activeStart=lunge.active[0],activeEnd=lunge.active[1],
                    damage=35,reach=1.25f,arc=35,knockback=.45f,hitstop=.03f,travelDistance=3.8f,
                    travelStart=lunge.movement_window[0],travelEnd=lunge.movement_window[1]},
                new MoveDefinition{id="hurt",duration=7f/30},new MoveDefinition{id="death",duration=1.2f}};
            EditorUtility.SetDirty(config); return config;
        }
        static GameObject Cube(string name,Vector3 position,Vector3 size,Material material,bool collider=true)
        {
            var go=GameObject.CreatePrimitive(PrimitiveType.Cube);go.name=name;go.transform.position=position;go.transform.localScale=size;
            go.GetComponent<Renderer>().sharedMaterial=material;
            if(!collider) UnityEngine.Object.DestroyImmediate(go.GetComponent<Collider>());
            return go;
        }
        static TrainingDummy Dummy(Vector3 position,Material material,Material wood)
        {
            var root=new GameObject("TrainingDummy");root.transform.position=position;
            var dummy=root.AddComponent<TrainingDummy>();
            var hurt=root.AddComponent<CapsuleCollider>();hurt.center=new Vector3(0,.9f,0);hurt.height=1.8f;hurt.radius=.32f;hurt.isTrigger=true;
            var body=GameObject.CreatePrimitive(PrimitiveType.Capsule);body.name="TargetBody";body.transform.SetParent(root.transform,false);
            body.transform.localPosition=new Vector3(0,1.05f,0);body.transform.localScale=new Vector3(.5f,.65f,.5f);
            UnityEngine.Object.DestroyImmediate(body.GetComponent<Collider>());body.GetComponent<Renderer>().sharedMaterial=material;
            var post=Cube("Post",position+Vector3.up*.45f,new Vector3(.15f,.9f,.15f),wood,false);post.transform.SetParent(root.transform,true);
            var arms=Cube("Target arms",position+Vector3.up*1.2f,new Vector3(1,.13f,.13f),wood,false);arms.transform.SetParent(root.transform,true);
            dummy.body=body.transform;dummy.bodyRenderer=body.GetComponent<Renderer>(); return dummy;
        }
        static Material Material(string name,Color color,float metal=0,float gloss=.1f)
        {
            string path=Base+"/Materials/"+name+".mat";
            var mat=AssetDatabase.LoadAssetAtPath<Material>(path);
            if(!mat){mat=new Material(Shader.Find("Standard"));AssetDatabase.CreateAsset(mat,path);}
            mat.color=color;mat.SetFloat("_Metallic",metal);mat.SetFloat("_Glossiness",gloss);EditorUtility.SetDirty(mat);return mat;
        }
        static Material UnlitMaterial(string name,Color color)
        {
            string path=Base+"/Materials/"+name+".mat";var mat=AssetDatabase.LoadAssetAtPath<Material>(path);
            if(!mat){mat=new Material(Shader.Find("Sprites/Default"));AssetDatabase.CreateAsset(mat,path);}
            mat.color=color;EditorUtility.SetDirty(mat);return mat;
        }
        static Material CharacterMaterial()
        {
            string root=Base+"/Art/";
            foreach(string name in new[]{"swordsman_basecolor_2048.png","swordsman_normal_2048.png","body_metallic_smoothness.png"})
            {
                var importer=(TextureImporter)AssetImporter.GetAtPath(root+name);
                importer.maxTextureSize=2048;importer.mipmapEnabled=true;
                importer.textureType=name.Contains("normal")?TextureImporterType.NormalMap:TextureImporterType.Default;
                importer.sRGBTexture=name.Contains("basecolor");importer.SaveAndReimport();
            }
            var mat=Material("SwordsmanAtlas",Color.white);
            mat.shader=Shader.Find("Swordsman/GraphicCharacter");
            mat.mainTexture=AssetDatabase.LoadAssetAtPath<Texture2D>(root+"swordsman_basecolor_2048.png");
            mat.SetTexture("_BumpMap",AssetDatabase.LoadAssetAtPath<Texture2D>(root+"swordsman_normal_2048.png"));
            mat.SetFloat("_BumpScale",.18f);mat.EnableKeyword("_NORMALMAP");
            mat.SetTexture("_MetallicGlossMap",AssetDatabase.LoadAssetAtPath<Texture2D>(root+"body_metallic_smoothness.png"));
            mat.SetFloat("_GlossMapScale",.6f);mat.EnableKeyword("_METALLICGLOSSMAP");
            EditorUtility.SetDirty(mat);return mat;
        }
        static Transform Find(Transform root,string name)
        {
            foreach(var child in root.GetComponentsInChildren<Transform>(true)) if(child.name==name)return child;
            return null;
        }
        static string Hash(string path)
        {
            using(var hash=SHA256.Create())return BitConverter.ToString(hash.ComputeHash(File.ReadAllBytes(path))).Replace("-","").ToLowerInvariant();
        }
    }
}
