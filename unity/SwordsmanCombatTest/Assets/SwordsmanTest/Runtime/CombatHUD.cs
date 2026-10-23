using UnityEngine;

namespace SwordsmanTest
{
    public class CombatHUD : MonoBehaviour
    {
        public CombatPlayer player;
        public bool showPanel=true;
        static CombatHUD active;
        GUIStyle title, label, small;
        float frameTime;
        public static bool PointerOverPanel()
        {
            Vector2 point = new Vector2(Input.mousePosition.x, Screen.height - Input.mousePosition.y);
            return active && active.showPanel && new Rect(14, 14, 330, 400).Contains(point);
        }
        void Awake(){active=this;}
        void Update() { frameTime = Mathf.Lerp(frameTime, Time.unscaledDeltaTime, .05f); if(Input.GetKeyDown(KeyCode.F1))showPanel=!showPanel; }
        void OnGUI()
        {
            if (!player || !player.tuning) return;
            if (title == null)
            {
                title = new GUIStyle(GUI.skin.label) { fontSize = 22, fontStyle = FontStyle.Bold };
                label = new GUIStyle(GUI.skin.label) { fontSize = 15 };
                small = new GUIStyle(GUI.skin.label) { fontSize = 13 };
            }
            if(showPanel){
            GUI.Box(new Rect(14, 14, 330, 400), GUIContent.none);
            GUILayout.BeginArea(new Rect(28, 24, 304, 380));
            GUILayout.Label("SWORDSMAN / COMBAT LAB", title);
            GUILayout.Label(player.State.ToUpperInvariant() + "  |  " + (player.Invulnerable ? "INVULNERABLE" : player.Phase), label);
            if (player.CurrentMove != null)
            {
                Rect bar = GUILayoutUtility.GetRect(290, 10);
                GUI.color = new Color(.17f, .20f, .25f); GUI.DrawTexture(bar, Texture2D.whiteTexture);
                GUI.color = player.Invulnerable ? Color.cyan : player.Active ? new Color(1, .45f, .12f) : new Color(.4f, .7f, 1);
                bar.width *= Mathf.Clamp01(player.ActionTime / player.CurrentMove.duration);
                GUI.DrawTexture(bar, Texture2D.whiteTexture); GUI.color = Color.white;
            }
            GUILayout.Label($"Hits: {player.TotalHits}    HP: {player.Health:0}    {(frameTime > 0 ? 1 / frameTime : 0):0} fps", small);
            GUILayout.Label($"Dash CD {player.DodgeCooldown:0.00}    Lunge CD {player.LungeCooldown:0.00}", small);
            GUILayout.Label(player.ComboQueued ? "NEXT STRIKE BUFFERED" : "Click again during recovery to chain", small);
            player.tuning.allowRecoveryDodgeCancel = GUILayout.Toggle(player.tuning.allowRecoveryDodgeCancel, " Allow recovery -> dodge cancel");
            player.showHitboxes = GUILayout.Toggle(player.showHitboxes, " Show active hit areas / i-frames (V)");
            GUILayout.Label($"Run speed: {player.tuning.runSpeed:0.0} m/s", small);
            player.tuning.runSpeed = GUILayout.HorizontalSlider(player.tuning.runSpeed, 2.3f, 5f);
            var dodge = player.tuning.Get("dodge");
            GUILayout.Label($"Dash distance: {dodge.travelDistance:0.0} m", small);
            dodge.travelDistance = GUILayout.HorizontalSlider(dodge.travelDistance, 1.5f, 4.5f);
            var lunge = player.tuning.Get("piercing_lunge");
            GUILayout.Label($"Lunge distance: {lunge.travelDistance:0.0} m", small);
            lunge.travelDistance = GUILayout.HorizontalSlider(lunge.travelDistance, 2f, 6f);
            if (GUILayout.Button("Reset player + targets (R)")) player.ResetArena();
            GUILayout.EndArea();
            }
            GUI.Box(new Rect(Screen.width / 2f - 370, Screen.height - 45, 740, 31),
                "WASD Move | LMB Combo | Space / Shift Dash | E / RMB Lunge | Wheel Zoom | F1 Settings");
            foreach (var target in player.targets)
            {
                Vector3 point = player.gameCamera.WorldToScreenPoint(target.transform.position + Vector3.up * 2.05f);
                if (point.z <= 0) continue;
                var rect = new Rect(point.x - 48, Screen.height - point.y, 96, 25);
                GUI.color=new Color(.06f,.045f,.04f,.95f);GUI.DrawTexture(rect,Texture2D.whiteTexture);
                GUI.color=new Color(.48f,.35f,.20f);GUI.DrawTexture(new Rect(rect.x,rect.y,rect.width,1),Texture2D.whiteTexture);
                GUI.color=Color.white;GUI.Label(new Rect(rect.x+7,rect.y+1,rect.width-8,20),$"{target.Health:0}/{target.maximumHealth:0}  x{target.Hits}",small);
                GUI.color=new Color(.16f,.035f,.035f);GUI.DrawTexture(new Rect(rect.x+5,rect.y+20,86,3),Texture2D.whiteTexture);
                GUI.color=new Color(.85f,.10f,.12f);GUI.DrawTexture(new Rect(rect.x+5,rect.y+20,86*Mathf.Clamp01(target.Health/target.maximumHealth),3),Texture2D.whiteTexture);GUI.color=Color.white;
            }
        }
    }
}
