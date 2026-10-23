using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace SwordsmanTest
{
    public class CombatSmokeTest : MonoBehaviour
    {
        public CombatPlayer player;
        [Serializable] public class Check { public string name; public bool passed; public string detail; }
        [Serializable] public class Report
        {
            public string unity, gpu, graphicsApi;
            public bool passed;
            public List<Check> checks = new List<Check>();
            public List<string> runtimeErrors = new List<string>();
        }
        Report report = new Report();
        string folder;
        float began;
        bool running, finished;
        const float Dt = 1f / 60;

        void Start()
        {
            string[] args = Environment.GetCommandLineArgs();
            if (Array.IndexOf(args, "-combatSmoke") < 0)
            {
                int ready=Array.IndexOf(args,"-captureReady");
                if(ready>=0)StartCoroutine(CaptureReady(args[ready+1]));
                return;
            }
            int output = Array.IndexOf(args, "-testOutput");
            folder = output >= 0 ? args[output + 1] : Path.Combine(Application.dataPath, "../Validation");
            Directory.CreateDirectory(folder);
            report.unity = Application.unityVersion; report.gpu = SystemInfo.graphicsDeviceName;
            report.graphicsApi = SystemInfo.graphicsDeviceType.ToString();
            player.externalDrive = true; player.Initialize(); running = true; began = Time.realtimeSinceStartup;
            Application.logMessageReceived += Log;
            QualitySettings.vSyncCount = 0; Application.targetFrameRate = 60;
            StartCoroutine(Run());
        }
        void Log(string message, string stack, LogType type)
        {
            if (type == LogType.Error || type == LogType.Exception || type == LogType.Assert)
                report.runtimeErrors.Add(message + "\n" + stack);
        }
        IEnumerator CaptureReady(string path)
        {
            yield return new WaitForSeconds(2);
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            ScreenCapture.CaptureScreenshot(path);
        }
        void Update()
        {
            if (running && !finished && Time.realtimeSinceStartup - began > 100)
            { CheckThat("watchdog", false, "Runtime test did not complete"); Finish(); }
        }
        void CheckThat(string name, bool passed, string detail)
        {
            report.checks.Add(new Check { name = name, passed = passed, detail = detail });
            Debug.Log("COMBAT_CHECK " + name + ": " + passed + " " + detail);
        }
        CombatInput InputFrame(bool attack = false, bool dodge = false, bool lunge = false, Vector2? movement = null)
        {
            return new CombatInput { aim = player.transform.position + Vector3.forward * 10,
                attack = attack, dodge = dodge, lunge = lunge, move = movement ?? Vector2.zero };
        }
        void Step(CombatInput input) { player.Tick(Dt, input); }
        void Shot(string name, float zoom = 0)
        {
            player.cameraRig.Snap();
            var camera = player.gameCamera;
            float previousZoom=camera.orthographicSize;
            if(zoom>0)camera.orthographicSize=zoom;
            var target = RenderTexture.GetTemporary(1280, 800, 24);
            var old = camera.targetTexture; var active = RenderTexture.active;
            camera.targetTexture = target; camera.Render(); RenderTexture.active = target;
            var image = new Texture2D(1280, 800, TextureFormat.RGB24, false);
            image.ReadPixels(new Rect(0, 0, 1280, 800), 0, 0); image.Apply();
            File.WriteAllBytes(Path.Combine(folder, name + ".png"), image.EncodeToPNG());
            camera.targetTexture = old; RenderTexture.active = active; RenderTexture.ReleaseTemporary(target); Destroy(image);
            camera.orthographicSize=previousZoom;
        }
        IEnumerator Run()
        {
            player.ResetArena();player.Teleport(new Vector3(-5,.025f,-4),Vector3.forward);
            Quaternion still=player.transform.rotation;
            for(int i=0;i<30;i++){Step(new CombatInput{aim=player.transform.position+Vector3.right*10});yield return null;}
            CheckThat("idle_ignores_mouse_facing",Quaternion.Angle(still,player.transform.rotation)<.1f,player.transform.forward.ToString());
            Vector3 expected=player.CameraMove(Vector2.right);
            for(int i=0;i<15;i++){Step(new CombatInput{move=Vector2.right,aim=player.transform.position-expected*10});yield return null;}
            CheckThat("run_faces_movement_not_mouse",Vector3.Dot(expected,player.transform.forward)>.999f,player.transform.forward.ToString());
            Quaternion stopped=player.transform.rotation;
            for(int i=0;i<30;i++){Step(new CombatInput{aim=player.transform.position-expected*10});yield return null;}
            CheckThat("stop_preserves_facing",Quaternion.Angle(stopped,player.transform.rotation)<.1f,player.transform.forward.ToString());
            Step(new CombatInput{attack=true,aim=player.transform.position+Vector3.back*10});
            CheckThat("attack_aims_at_cursor",player.State=="attack_1" && Vector3.Dot(Vector3.back,player.transform.forward)>.999f,player.transform.forward.ToString());
            player.ResetArena();player.Teleport(new Vector3(-5,.025f,-4),Vector3.forward);
            Step(new CombatInput{dodge=true,aim=player.transform.position+Vector3.right*10});
            CheckThat("stationary_dodge_uses_facing",player.State=="dodge" && Vector3.Dot(Vector3.forward,player.transform.forward)>.999f,player.transform.forward.ToString());
            player.ResetArena();player.Teleport(new Vector3(-5,.025f,-4),Vector3.forward);
            Step(new CombatInput{lunge=true,aim=player.transform.position+Vector3.right*10});
            CheckThat("lunge_aims_at_cursor",player.State=="piercing_lunge" && Vector3.Dot(Vector3.right,player.transform.forward)>.999f,player.transform.forward.ToString());
            player.ResetArena(); player.Teleport(new Vector3(0, .025f, -1.1f), Vector3.forward);
            int clipCount = player.animationPlayer.clips.Length;
            CheckThat("nine_imported_clips", clipCount == 9, clipCount.ToString());
            var visited = new HashSet<string>(); string queued = ""; bool shot = false;
            for (int i = 0; i < 150; i++)
            {
                bool chain = (player.State == "attack_1" || player.State == "attack_2") &&
                    player.ActionTime > .18f && queued != player.State;
                if (chain) queued = player.State;
                Step(InputFrame(attack: i == 0 || chain)); visited.Add(player.State);
                if(player.State=="attack_3" && player.ActionTime>.22f && player.ActionTime<.24f)Shot("unity_combo_sweep",1.8f);
                if (player.State == "attack_3" && player.ActionTime > .33f && !shot) { Shot("unity_combo_impact"); shot = true; }
                yield return null;
            }
            CheckThat("distinct_three_hit_combo", visited.Contains("attack_1") && visited.Contains("attack_2") && visited.Contains("attack_3"), string.Join(",", visited));
            CheckThat("each_strike_hits_once", player.targets[0].Hits == 3, "hits=" + player.targets[0].Hits);
            CheckThat("combo_damage_20_25_45", Mathf.Abs(player.targets[0].Health - 110) < .01f, "hp=" + player.targets[0].Health);
            CheckThat("combo_returns_to_locomotion", player.State == "locomotion", player.State);

            player.ResetArena(); Vector3 runStart = player.transform.position;
            for (int i = 0; i < 90; i++)
            {
                Step(InputFrame(movement: new Vector2(1, 0)));
                if (i == 35) Shot("unity_running");
                yield return null;
            }
            float runDistance = Vector3.ProjectOnPlane(player.transform.position - runStart, Vector3.up).magnitude;
            CheckThat("run_moves_character", runDistance > player.tuning.runSpeed*1.25f && runDistance < player.tuning.runSpeed*1.51f, "distance=" + runDistance+", speed="+player.tuning.runSpeed);
            CheckThat("run_clip_plays", player.animationPlayer.Current == "run", player.animationPlayer.Current);
            // Still running: a strike along the stride slides on instead of stopping dead, then settles.
            Vector3 strideDirection = player.CameraMove(Vector2.right), slideStart = player.transform.position;
            Step(new CombatInput { attack = true, move = new Vector2(1, 0), aim = player.transform.position + strideDirection * 10 });
            for (int i = 0; i < 17; i++) { Step(InputFrame()); yield return null; }
            float slide = Vector3.Dot(player.transform.position - slideStart, strideDirection);
            float expectedSlide = player.tuning.runSpeed * player.tuning.runAttackCarry * player.tuning.runAttackStopTime * .5f;
            CheckThat("run_attack_keeps_momentum", player.State == "attack_1" && Mathf.Abs(slide - expectedSlide) < .15f,
                "slide=" + slide + ", expected=" + expectedSlide);

            player.ResetArena(); player.Teleport(new Vector3(-5, .025f, -4), Vector3.forward);
            Vector3 dodgeStart = player.transform.position; bool invulnerabilityTested = false;
            for (int i = 0; i < 40; i++)
            {
                Step(InputFrame(dodge: i == 0));
                if(player.State=="dodge" && player.ActionTime>.14f && player.ActionTime<.16f)Shot("unity_dash_burst",1.8f);
                if (player.Invulnerable && !invulnerabilityTested)
                {
                    invulnerabilityTested = true;
                    CheckThat("dodge_iframes_reject_damage", !player.TryDamage(10) && player.Health == 100, "hp=" + player.Health);
                    Shot("unity_dodge_iframes");
                }
                yield return null;
            }
            float dodgeDistance = Vector3.ProjectOnPlane(player.transform.position - dodgeStart, Vector3.up).magnitude;
            CheckThat("dodge_code_distance", Mathf.Abs(dodgeDistance - player.tuning.Get("dodge").travelDistance) < .10f, dodgeDistance.ToString());
            CheckThat("dodge_iframe_window_seen", invulnerabilityTested, "window entered");
            CheckThat("damage_outside_iframes", player.TryDamage(10) && player.Health == 90, "hp=" + player.Health);

            player.ResetArena(); player.Teleport(new Vector3(-5, .025f, -4), Vector3.forward);
            Step(InputFrame(attack: true));
            for (int i = 0; i < 3; i++) { Step(InputFrame()); yield return null; }
            Step(InputFrame(dodge: true));
            CheckThat("startup_dodge_cancel_blocked", player.State == "attack_1", player.State);
            for (int i = 0; i < 12; i++) { Step(InputFrame()); yield return null; }
            Step(InputFrame(dodge: true));
            CheckThat("recovery_dodge_cancel_allowed", player.State == "dodge" && player.DodgeCancels == 1, player.State);

            player.ResetArena(); player.Teleport(new Vector3(-5,.025f,-4),Vector3.forward);
            player.tuning.allowRecoveryDodgeCancel=false;
            Step(InputFrame(attack:true));
            for(int i=0;i<17;i++){Step(InputFrame());yield return null;}
            Step(InputFrame(dodge:true));
            CheckThat("cancel_toggle_off_blocks_recovery",player.State=="attack_1" && player.DodgeCancels==0,player.State);
            player.tuning.allowRecoveryDodgeCancel=true;

            player.ResetArena(); player.Teleport(new Vector3(0, .025f, -2.2f), Vector3.forward);
            Vector3 lungeStart = player.transform.position;
            for (int i = 0; i < 55; i++)
            {
                Step(InputFrame(lunge: i == 0));
                if (player.State == "piercing_lunge" && player.ActionTime > .23f && player.ActionTime < .26f) Shot("unity_piercing_lunge");
                yield return null;
            }
            float lungeDistance = Vector3.ProjectOnPlane(player.transform.position - lungeStart, Vector3.up).magnitude;
            CheckThat("lunge_code_distance", Mathf.Abs(lungeDistance - player.tuning.Get("piercing_lunge").travelDistance) < .10f, lungeDistance.ToString());
            CheckThat("lunge_hits_targets_in_line", player.targets[0].Hits == 1 && player.targets[1].Hits == 1, player.targets[0].Hits + "/" + player.targets[1].Hits);

            player.ResetArena(); player.Teleport(new Vector3(7.5f, .025f, 0), Vector3.right);
            for (int i = 0; i < 45; i++)
            {
                var input = InputFrame(lunge: i == 0); input.aim = player.transform.position + Vector3.right * 10;
                Step(input); yield return null;
            }
            CheckThat("lunge_stops_at_wall", player.transform.position.x < 8.65f && player.transform.position.x > 7.6f, player.transform.position.ToString());
            player.ResetArena(); player.Teleport(new Vector3(7.5f,.025f,0),Vector3.right);
            for(int i=0;i<35;i++)
            {
                var input=InputFrame(dodge:i==0);input.aim=player.transform.position+Vector3.right*10;
                Step(input);yield return null;
            }
            CheckThat("dodge_stops_at_wall",player.transform.position.x<8.65f && player.transform.position.x>7.6f,player.transform.position.ToString());
            player.ResetArena(); Shot("unity_arena"); Shot("unity_character_detail",1.7f);
            ScreenCapture.CaptureScreenshot(Path.Combine(folder,"unity_screen_with_hud.png"));
            for(int i=0;i<8;i++)yield return null;
            Finish();
        }
        void Finish()
        {
            if (finished) return; finished = true;
            report.passed = report.runtimeErrors.Count == 0 && report.checks.TrueForAll(c => c.passed);
            File.WriteAllText(Path.Combine(folder, "runtime-test-report.json"), JsonUtility.ToJson(report, true));
            Debug.Log("COMBAT_SMOKE_FINISHED " + report.passed);
            Application.Quit(report.passed ? 0 : 1);
        }
    }
}
