using UnityEngine;

namespace SwordsmanTest
{
    public class CombatCamera : MonoBehaviour
    {
        public Transform target;
        public Vector3 offset = new Vector3(7, 9, 7);
        float trauma;
        public void Shake(float strength) { trauma = Mathf.Max(trauma, strength); }
        public void Snap()
        {
            if (!target) return;
            transform.position = target.position + offset;
            transform.rotation = Quaternion.LookRotation(target.position + Vector3.up * .7f - transform.position);
        }
        void LateUpdate()
        {
            if (!target) return;
            float dt = Time.unscaledDeltaTime;
            var camera=GetComponent<Camera>();
            if(camera)camera.orthographicSize=Mathf.Clamp(camera.orthographicSize-Input.mouseScrollDelta.y*.3f,2.5f,6f);
            Vector3 destination = target.position + offset;
            transform.position = Vector3.Lerp(transform.position, destination, 1 - Mathf.Exp(-9 * dt));
            transform.rotation = Quaternion.LookRotation(target.position + Vector3.up * .7f - transform.position);
            if (trauma > 0)
            {
                transform.position += transform.right * Mathf.Sin(Time.unscaledTime * 113) * trauma;
                trauma = Mathf.Max(0, trauma - dt * .7f);
            }
        }
    }
}
