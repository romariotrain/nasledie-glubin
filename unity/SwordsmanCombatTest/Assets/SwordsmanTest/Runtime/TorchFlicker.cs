using UnityEngine;
namespace SwordsmanTest
{
    public class TorchFlicker : MonoBehaviour
    {
        public Light fireLight;
        public Transform flame;
        public float intensity=3.4f,phase;
        Vector3 initial;
        void Awake(){if(flame)initial=flame.localScale;}
        void Update()
        {
            float t=Time.time+phase;
            float pulse=.92f+.055f*Mathf.Sin(t*7.3f)+.025f*Mathf.Sin(t*17.1f);
            if(fireLight)fireLight.intensity=intensity*pulse;
            if(flame)flame.localScale=Vector3.Scale(initial,new Vector3(1+.035f*Mathf.Sin(t*8),pulse,1));
        }
    }
}
