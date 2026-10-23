using System;
using UnityEngine;

namespace SwordsmanTest
{
    // Visual-style test, attached to the main camera at runtime so no scene or prefab changes are needed.
    // F2 cycles the modes; the command line "-style N" and "-pixel N" pick them for builds and screenshots.
    //   0  current look
    //   1  ink outline from depth+normals, rim light, hero key light from the side
    //   2  mode 1 rendered at 1/N resolution and upscaled without filtering (crisp, painted edges)
    // F3 / "-flat 0|1" swaps the hero's painted basecolour for the flat colour-zone map and drops normal detail.
    [RequireComponent(typeof(Camera))]
    public class StylePost : MonoBehaviour
    {
        // Defaults keep the original look; the test variants stay available on F2/F3 or the command line.
        public static int Mode = 0;
        public static int PixelScale = 2;
        public static bool Flat = false;
        // Sharpness tests: negative bias samples sharper mip levels of the hero maps; NoMsaa turns camera MSAA off.
        public static float MipBias = 0;
        public static bool NoMsaa = false;
        [Range(.5f, 3)] public float outlineWidth = 1.6f;
        public float depthEdge = .12f;
        [Tooltip("Inner lines where neighbouring normals differ more than this cosine; low = only sharp folds")]
        [Range(-1, 1)] public float normalEdge = .1f;
        public Color ink = new Color(.03f, .02f, .035f, 1);
        [Range(0, 2)] public float rim = .55f;
        [Tooltip("Hero key yaw relative to the camera, degrees; ~90 lights the hero from the side")] public float keyYaw = 105;
        [Range(10, 80)] public float keyPitch = 32;
        Camera view; Material post; Light heroKey; Quaternion originalKey; bool keyCaptured;
        Renderer hero; Texture2D flatMap; MaterialPropertyBlock heroBlock;
        static readonly int RimId = Shader.PropertyToID("_StyleRim"), BandsId = Shader.PropertyToID("_StyleBands");

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Attach()
        {
            string[] args = Environment.GetCommandLineArgs();
            int style = Array.IndexOf(args, "-style"); if (style >= 0 && style + 1 < args.Length) int.TryParse(args[style + 1], out Mode);
            int pixel = Array.IndexOf(args, "-pixel"); if (pixel >= 0 && pixel + 1 < args.Length) int.TryParse(args[pixel + 1], out PixelScale);
            int flat = Array.IndexOf(args, "-flat"); if (flat >= 0 && flat + 1 < args.Length) Flat = args[flat + 1] != "0";
            int mip = Array.IndexOf(args, "-mipbias"); if (mip >= 0 && mip + 1 < args.Length) float.TryParse(args[mip + 1], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out MipBias);
            int msaa = Array.IndexOf(args, "-msaa"); if (msaa >= 0 && msaa + 1 < args.Length) NoMsaa = args[msaa + 1] == "0";
            var camera = Camera.main;
            if (camera && !camera.GetComponent<StylePost>()) camera.gameObject.AddComponent<StylePost>();
        }

        void Awake()
        {
            view = GetComponent<Camera>();
            var shader = Resources.Load<Shader>("StylePost");
            if (shader && shader.isSupported) post = new Material(shader) { hideFlags = HideFlags.HideAndDontSave };
            var keyObject = GameObject.Find("Hero key (character only)");
            if (keyObject) { heroKey = keyObject.GetComponent<Light>(); originalKey = heroKey.transform.rotation; keyCaptured = true; }
            var player = FindAnyObjectByType<CombatPlayer>();
            if (player) hero = player.GetComponentInChildren<SkinnedMeshRenderer>();
            flatMap = Resources.Load<Texture2D>("StyleTest/hero_flat_v001");
            if (NoMsaa) view.allowMSAA = false;
            if (MipBias != 0 && hero)
            {
                foreach (var m in hero.sharedMaterials)
                    foreach (var id in new[] { "_MainTex", "_BumpMap" })
                        if (m && m.HasProperty(id) && m.GetTexture(id)) m.GetTexture(id).mipMapBias = MipBias;
                if (flatMap) flatMap.mipMapBias = MipBias;
            }
            Apply();
        }

        void Update()
        {
            if (Input.GetKeyDown(KeyCode.F2)) { Mode = (Mode + 1) % 3; Apply(); }
            if (Input.GetKeyDown(KeyCode.F3)) { Flat = !Flat; Apply(); }
            if (Mode > 0 && heroKey)
            {
                // Keep the key at a fixed angle to the view, so the camera always sees a lit and a shadowed side.
                Vector3 flat = Vector3.ProjectOnPlane(transform.forward, Vector3.up).normalized;
                heroKey.transform.rotation = Quaternion.LookRotation(Quaternion.AngleAxis(keyYaw, Vector3.up) * flat) *
                                             Quaternion.Euler(keyPitch, 0, 0);
            }
        }

        void Apply()
        {
            view.depthTextureMode = Mode > 0 ? view.depthTextureMode | DepthTextureMode.DepthNormals : DepthTextureMode.None;
            Shader.SetGlobalFloat(RimId, Mode > 0 ? rim : 0);
            Shader.SetGlobalFloat(BandsId, Mode > 0 ? 1 : 0);
            if (Mode == 0 && keyCaptured) heroKey.transform.rotation = originalKey;
            if (hero && flatMap)
            {
                heroBlock ??= new MaterialPropertyBlock();
                hero.GetPropertyBlock(heroBlock);
                if (Flat) { heroBlock.SetTexture("_MainTex", flatMap); heroBlock.SetFloat("_BumpScale", 0); heroBlock.SetFloat("_RedBoost", 1); }
                else heroBlock.Clear();
                hero.SetPropertyBlock(heroBlock);
            }
        }

        // Opaque-only: ink and pixelation happen before slash arcs and sparks, which stay smooth on top.
        [ImageEffectOpaque]
        void OnRenderImage(RenderTexture source, RenderTexture destination)
        {
            if (Mode == 0 || !post) { Graphics.Blit(source, destination); return; } // original look: plain copy
            // At 1/N resolution one texel is already N screen pixels wide.
            post.SetFloat("_OutlineWidth", Mode == 2 ? Mathf.Max(1, outlineWidth / Mathf.Max(1, PixelScale) * 1.25f) : outlineWidth);
            post.SetFloat("_DepthEdge", depthEdge);
            post.SetFloat("_NormalEdge", normalEdge); post.SetColor("_InkColor", ink);
            if (Mode == 1) { Graphics.Blit(source, destination, post, 0); return; }
            int scale = Mathf.Max(1, PixelScale);
            int w = Mathf.Max(1, source.width / scale), h = Mathf.Max(1, source.height / scale);
            var low = RenderTexture.GetTemporary(w, h, 0, source.format); low.filterMode = FilterMode.Point;
            var inked = RenderTexture.GetTemporary(w, h, 0, source.format); inked.filterMode = FilterMode.Point;
            source.filterMode = FilterMode.Point;
            Graphics.Blit(source, low, post, 1);
            Graphics.Blit(low, inked, post, 0);
            Graphics.Blit(inked, destination, post, 1);
            RenderTexture.ReleaseTemporary(low); RenderTexture.ReleaseTemporary(inked);
        }

        void OnDestroy()
        {
            Shader.SetGlobalFloat(RimId, 0); Shader.SetGlobalFloat(BandsId, 0);
            if (keyCaptured && heroKey) heroKey.transform.rotation = originalKey;
            if (post) Destroy(post);
        }
    }
}
